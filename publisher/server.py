"""Individual-use EDC dummy publisher. No Eclipse EDC runtime is implemented."""

import argparse
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
MAX_RDF = 2_000_000
MAX_REQUEST = 12_000_000
FORMATS = {
    ".ttl": "text/turtle",
    ".jsonld": "application/ld+json",
    ".json": "application/ld+json",
    ".rdf": "application/rdf+xml",
    ".nt": "application/n-triples",
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def prepare(payload):
    if not isinstance(payload, dict):
        raise TypeError("Expected a publication object")
    url, token, rdf, filename = (
        payload.get(key) for key in ("url", "token", "rdf", "filename")
    )
    if not all(isinstance(value, str) for value in (url, token, rdf, filename)):
        raise ValueError("Catalog URL, token and RDF file are required")
    url, token = url.strip().rstrip("/"), token.strip()
    parsed = urlsplit(url)
    _ = parsed.port
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use a catalog URL without credentials, query or fragment")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError(
            "Remote catalogs require HTTPS; HTTP is allowed only on localhost"
        )
    if parsed.path == "":
        url += "/catalog"
    elif parsed.path != "/catalog":
        raise ValueError("Use the catalog origin or its /catalog endpoint")
    if (
        not token
        or not token.isascii()
        or any(character.isspace() for character in token)
    ):
        raise ValueError("Enter your participant token without spaces")
    content_type = FORMATS.get(Path(filename).suffix.lower())
    if not content_type:
        raise ValueError("Choose a .ttl, .jsonld, .json, .rdf or .nt file")
    body = rdf.encode("utf-8")
    if not body or len(body) > MAX_RDF:
        raise ValueError("Choose a nonempty RDF file no larger than 2 MB")
    return url, token, body, content_type


def publish(payload, opener=None):
    url, token, body, content_type = prepare(payload)
    request_id = "dummy-" + uuid4().hex
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": content_type,
            "X-Request-Id": request_id,
            "User-Agent": "edc-dummy-publisher/1.0",
        },
    )
    opener = opener or build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            status, raw = response.status, response.read(262145)
    except HTTPError as error:
        status, raw = error.code, error.read(262145)
    if len(raw) > 262144:
        raise ValueError("Catalog response exceeded the display limit")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        result = {"detail": raw.decode("utf-8", errors="replace")}
    # Never reflect a participant credential, even if a remote endpoint echoes it.
    result = redact(result, token)
    return {"status": status, "request_id": request_id, "response": result}


def redact(value, token):
    if isinstance(value, str):
        return value.replace(token, "[redacted]")
    if isinstance(value, list):
        return [redact(item, token) for item in value]
    if isinstance(value, dict):
        return {redact(key, token): redact(item, token) for key, item in value.items()}
    return value


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send(self, status, body, content_type="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def local_host(self):
        return self.headers.get("Host") in {
            f"localhost:{self.server.server_port}",
            f"127.0.0.1:{self.server.server_port}",
        }

    def do_GET(self):
        if not self.local_host():
            return self.send(403, {"detail": "Open this publisher through localhost"})
        files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript"),
            "/style.css": ("style.css", "text/css"),
        }
        if self.path == "/session":
            return self.send(200, {"csrf": self.server.csrf})
        if self.path not in files:
            return self.send(404, {"detail": "Not found"})
        name, content_type = files[self.path]
        self.send(200, (ROOT / name).read_bytes(), content_type)

    def do_POST(self):
        origin = self.headers.get("Origin", "")
        expected_origin = "http://" + self.headers.get("Host", "")
        if (
            not self.local_host()
            or origin != expected_origin
            or not secrets.compare_digest(
                self.headers.get("X-Publisher-CSRF", "").encode("utf-8"),
                self.server.csrf.encode("ascii"),
            )
        ):
            return self.send(
                403, {"detail": "Reload the local publisher page and try again"}
            )
        if self.path != "/publish":
            return self.send(404, {"detail": "Not found"})
        if self.headers.get("Content-Type") != "application/json":
            return self.send(415, {"detail": "Expected JSON"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_REQUEST:
                return self.send(413, {"detail": "Publication is too large or empty"})
            self.connection.settimeout(40)
            payload = json.loads(self.rfile.read(size))
            result = publish(payload)
        except (TypeError, ValueError, UnicodeError):
            return self.send(
                400,
                {
                    "detail": "Check the catalog URL, token and file. Use HTTPS remotely and a supported UTF-8 RDF file up to 2 MB."
                },
            )
        except (URLError, OSError):
            return self.send(
                502,
                {
                    "detail": "Catalog could not be reached. Check the URL, internet connection and certificate."
                },
            )
        self.send(200, result)


def create_server(port=8787, bind="127.0.0.1"):
    server = ThreadingHTTPServer((bind, port), Handler)
    server.csrf = secrets.token_hex(32)
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--container",
        action="store_true",
        help="Bind inside Docker; publish its port to host loopback only",
    )
    args = parser.parse_args()
    server = create_server(args.port, "0.0.0.0" if args.container else "127.0.0.1")
    print(f"EDC dummy publisher: http://127.0.0.1:{server.server_port}", flush=True)
    print(
        "Individual testing/demo only. No Eclipse EDC or DSP. Press Ctrl+C to stop.",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
