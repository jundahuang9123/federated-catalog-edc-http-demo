"""Reject placeholder or unsafe settings in the public demo deployment."""

import os
import re
from urllib.parse import urlsplit

from core.shared.demo_participants import ParticipantConfigurationError, parse_demo_participants


def _require_positive_number(name: str, default: str, *, integer: bool) -> None:
    raw_value = os.getenv(name, default)
    try:
        value = int(raw_value) if integer else float(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive number") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be a positive number")


def validate_deployment() -> None:
    if os.getenv("CATALOG_DEPLOYMENT") != "production":
        return
    if os.getenv("CATALOG_MODE", "").lower() != "http-demo":
        raise RuntimeError("CATALOG_MODE must be http-demo for this demonstrator")

    public_value = os.getenv("CATALOG_PUBLIC_URL", "")
    public = urlsplit(public_value)
    if (
        public.scheme != "https"
        or not public.hostname
        or "REPLACE" in public_value
        or public.username is not None
        or public.password is not None
    ):
        raise RuntimeError("CATALOG_PUBLIC_URL must be configured with an HTTPS URL")
    if public.path not in ("", "/") or public.query or public.fragment:
        raise RuntimeError("CATALOG_PUBLIC_URL must be an origin without a path, query or fragment")

    try:
        participants = parse_demo_participants(os.getenv("EDC_DEMO_PARTICIPANTS", ""))
    except ParticipantConfigurationError as exc:
        raise RuntimeError(str(exc)) from exc
    if len(participants) < 2:
        raise RuntimeError("Configure at least two simulated participants for the federated demo")
    for token in participants.values():
        if not re.fullmatch(r"[a-fA-F0-9]{64,}", token) or "REPLACE" in token:
            raise RuntimeError(
                "Use a unique token with at least 32 random bytes for each participant"
            )

    origins = os.getenv("CATALOG_CORS_ORIGINS", "")
    for value in origins.split(",") if origins else []:
        origin = urlsplit(value.strip())
        if (
            origin.scheme != "https"
            or not origin.hostname
            or origin.username is not None
            or origin.password is not None
            or origin.path not in ("", "/")
            or origin.query
            or origin.fragment
        ):
            raise RuntimeError("Configured production CORS origins must be explicit HTTPS origins")
    password = os.getenv("FUSEKI_PASSWORD", "")
    if (
        len(password) < 48
        or "REPLACE" in password
        or not all(character in "0123456789abcdefABCDEF" for character in password)
    ):
        raise RuntimeError("Configure at least 24 random bytes as a hexadecimal Fuseki password")

    for name, default in (
        ("CATALOG_MAX_INGEST_BYTES", "2097152"),
        ("SPARQL_MAX_REQUEST_BYTES", "32768"),
        ("SPARQL_MAX_ROWS", "500"),
        ("SPARQL_MAX_RESPONSE_BYTES", "2097152"),
    ):
        _require_positive_number(name, default, integer=True)
    for name, default in (
        ("CATALOG_STARTUP_WAIT_SECONDS", "60"),
        ("CATALOG_STARTUP_RETRY_SECONDS", "1"),
        ("FUSEKI_TIMEOUT_SECONDS", "10"),
        ("SPARQL_TIMEOUT_SECONDS", "10"),
    ):
        _require_positive_number(name, default, integer=False)
