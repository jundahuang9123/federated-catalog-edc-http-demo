#!/usr/bin/env python3
"""Simulate the final HTTP delivery step of an EDC-side adapter.

This tool does not implement Eclipse EDC, DSP, contract negotiation, policy
enforcement, or data-plane orchestration.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

SUPPORTED_SUFFIXES = {
    ".json": "application/ld+json",
    ".jsonld": "application/ld+json",
    ".n3": "text/n3",
    ".nq": "application/n-quads",
    ".nt": "application/n-triples",
    ".rdf": "application/rdf+xml",
    ".trig": "application/trig",
    ".ttl": "text/turtle",
    ".xml": "application/rdf+xml",
}


class SimulatorConfigurationError(ValueError):
    pass


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_token(participant_id: str | None, env_file: Path) -> str:
    direct_token = os.getenv("EDC_SIMULATOR_TOKEN", "").strip()
    if direct_token:
        return direct_token
    if not participant_id:
        raise SimulatorConfigurationError(
            "Choose --participant or set EDC_SIMULATOR_TOKEN in the environment"
        )

    raw_mapping = os.getenv("EDC_DEMO_PARTICIPANTS", "")
    if not raw_mapping:
        raw_mapping = _read_env_file(env_file).get("EDC_DEMO_PARTICIPANTS", "")
    try:
        participants = json.loads(raw_mapping)
    except json.JSONDecodeError as exc:
        raise SimulatorConfigurationError(
            f"Could not read EDC_DEMO_PARTICIPANTS from {env_file}"
        ) from exc
    if not isinstance(participants, dict) or not isinstance(
        participants.get(participant_id), str
    ):
        raise SimulatorConfigurationError(
            f"Participant is not configured: {participant_id}"
        )
    token = participants[participant_id].strip()
    if not token or "REPLACE" in token:
        raise SimulatorConfigurationError(
            f"Participant token is not configured: {participant_id}"
        )
    return token


def validate_catalog_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        raise SimulatorConfigurationError("Catalog URL is invalid") from exc
    local_http = parsed.scheme == "http" and hostname in {
        "localhost",
        "127.0.0.1",
    }
    if parsed.scheme != "https" and not local_http:
        raise SimulatorConfigurationError(
            "Use an HTTPS catalog URL; plain HTTP is allowed only for localhost"
        )
    if (
        not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise SimulatorConfigurationError(
            "Catalog URL must be an absolute endpoint URL"
        )
    if parsed.path.rstrip("/") != "/catalog":
        raise SimulatorConfigurationError("Catalog URL path must be /catalog")
    return value.rstrip("/")


def publish_catalog(
    *,
    catalog_url: str,
    rdf_path: Path,
    token: str,
    request_id: str,
    timeout: float,
    opener: Callable = urlopen,
) -> tuple[int, dict[str, object]]:
    content_type = SUPPORTED_SUFFIXES.get(rdf_path.suffix.lower())
    if content_type is None:
        raise SimulatorConfigurationError(
            f"Unsupported RDF file extension: {rdf_path.suffix or '<none>'}"
        )
    body = rdf_path.read_bytes()
    request = Request(
        validate_catalog_url(catalog_url),
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
            "User-Agent": "edc-http-adapter-simulator/1.0",
            "X-Request-Id": request_id,
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            response_body = response.read()
            status = response.status
    except HTTPError as exc:
        response_body = exc.read()
        status = exc.code
    try:
        payload = json.loads(response_body) if response_body else {}
    except json.JSONDecodeError:
        payload = {"detail": response_body.decode("utf-8", errors="replace")}
    return status, payload if isinstance(payload, dict) else {"response": payload}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Post DCAT/RDF through the custom HTTP boundary an EDC-side adapter could call. "
            "This simulator does not implement Eclipse EDC or DSP."
        )
    )
    parser.add_argument(
        "--catalog-url",
        default=os.getenv("CATALOG_URL", ""),
        help="Full /catalog endpoint URL (or set CATALOG_URL)",
    )
    parser.add_argument(
        "--participant", help="Participant ID used to select a token from .env"
    )
    parser.add_argument(
        "--rdf", required=True, type=Path, help="DCAT/RDF file to publish"
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--request-id", default="sim-" + uuid4().hex[:16])
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if not args.catalog_url:
            raise SimulatorConfigurationError(
                "Provide --catalog-url or set CATALOG_URL"
            )
        if not args.rdf.is_file():
            raise SimulatorConfigurationError(f"RDF file does not exist: {args.rdf}")
        if args.timeout <= 0:
            raise SimulatorConfigurationError("Timeout must be greater than zero")
        token = resolve_token(args.participant, args.env_file)
        print(
            "Simulation only: no Eclipse EDC, DSP, negotiation, policy, or data plane is running."
        )
        print(f"Sending {args.rdf} to {args.catalog_url}")
        status, payload = publish_catalog(
            catalog_url=args.catalog_url,
            rdf_path=args.rdf,
            token=token,
            request_id=args.request_id,
            timeout=args.timeout,
        )
    except SimulatorConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except (OSError, URLError) as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 1

    print(f"HTTP {status}")
    if payload.get("accepted"):
        print(f"Participant: {payload.get('participant_id', '-')}")
        print(f"Graph: {payload.get('graph', '-')}")
        print(f"Request ID: {payload.get('request_id', args.request_id)}")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
