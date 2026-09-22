"""Exercise the local browser boundary and the real outgoing HTTP request."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server


class Receiver(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        self.server.received.append(
            (
                self.path,
                self.headers,
                self.rfile.read(int(self.headers["Content-Length"])),
            )
        )
        self.send_response(self.server.status)
        if self.server.status == 302:
            self.send_header("Location", "/redirect-target")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "accepted": self.server.status == 200,
                    "echo": self.headers["Authorization"],
                }
            ).encode()
        )


class PublisherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
        cls.local = server.create_server(0)
        cls.threads = []
        for service in (cls.upstream, cls.local):
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            cls.threads.append(thread)
        cls.origin = f"http://127.0.0.1:{cls.local.server_port}"

    @classmethod
    def tearDownClass(cls):
        for service in (cls.upstream, cls.local):
            service.shutdown()
            service.server_close()
        for thread in cls.threads:
            thread.join()

    def setUp(self):
        self.upstream.status = 200
        self.upstream.received = []
        self.payload = {
            "url": f"http://127.0.0.1:{self.upstream.server_port}",
            "token": "demo-token",
            "filename": "catalog.ttl",
            "rdf": '<urn:a> <urn:b> "demo" .',
        }

    def test_browser_to_remote_publication(self):
        with urlopen(self.origin + "/session") as response:
            csrf = json.load(response)["csrf"]
        request = Request(
            self.origin + "/publish",
            data=json.dumps(self.payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Origin": self.origin,
                "X-Publisher-CSRF": csrf,
            },
        )
        with urlopen(request) as response:
            result = json.load(response)
        self.assertEqual(result["status"], 200)
        self.assertTrue(result["response"]["accepted"])
        self.assertNotIn(self.payload["token"], json.dumps(result))
        path, headers, body = self.upstream.received[0]
        self.assertEqual(path, "/catalog")
        self.assertEqual(body, self.payload["rdf"].encode())
        self.assertEqual(headers["Authorization"], "Bearer demo-token")
        self.assertEqual(headers["Content-Type"], "text/turtle")
        self.assertIsNone(headers.get("X-Participant-Id"))
        self.assertEqual(headers["X-Request-Id"], result["request_id"])

    def test_remote_rejection_is_preserved(self):
        for status in (401, 422, 502):
            self.upstream.status = status
            self.assertEqual(server.publish(self.payload)["status"], status)

    def test_redirect_not_followed(self):
        self.upstream.status = 302
        self.assertEqual(server.publish(self.payload)["status"], 302)
        self.assertEqual(len(self.upstream.received), 1)

    def test_cross_origin_and_missing_csrf_rejected(self):
        for origin, csrf in [
            ("http://evil.invalid", self.local.csrf),
            (self.origin, ""),
            (self.origin, "é"),
        ]:
            request = Request(
                self.origin + "/publish",
                data=b"{}",
                headers={
                    "Origin": origin,
                    "X-Publisher-CSRF": csrf,
                    "Content-Type": "application/json",
                },
            )
            with self.assertRaises(HTTPError) as caught:
                urlopen(request)
            self.assertEqual(caught.exception.code, 403)
        self.assertEqual(self.upstream.received, [])

    def test_host_and_static_file_boundaries(self):
        for path, headers, status in [
            ("/session", {"Host": "evil.invalid"}, 403),
            ("/server.py", {}, 404),
        ]:
            with self.assertRaises(HTTPError) as caught:
                urlopen(Request(self.origin + path, headers=headers))
            self.assertEqual(caught.exception.code, status)
        with urlopen(self.origin) as response:
            self.assertIn(b"EDC dummy publisher", response.read())
            self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_invalid_inputs(self):
        for key, value in [
            ("url", "http://example.com"),
            ("url", "https://user:pass@example.com"),
            ("url", "https://example.com/other"),
            ("url", "https://example.com?token=x"),
            ("token", "a\nb"),
            ("rdf", ""),
            ("rdf", "x" * (server.MAX_RDF + 1)),
            ("filename", "file.exe"),
        ]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                server.prepare({**self.payload, key: value})

    def test_formats_and_origin_normalization(self):
        for suffix, content_type in server.FORMATS.items():
            url, _, _, actual = server.prepare(
                {
                    **self.payload,
                    "url": "https://example.com/",
                    "filename": "file" + suffix,
                }
            )
            self.assertEqual(url, "https://example.com/catalog")
            self.assertEqual(actual, content_type)

    def test_redaction_handles_json_characters(self):
        self.assertEqual(
            server.redact({"a": ['quote"', 1]}, '"'), {"a": ["quote[redacted]", 1]}
        )


if __name__ == "__main__":
    unittest.main()
