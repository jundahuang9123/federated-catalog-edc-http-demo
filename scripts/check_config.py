#!/usr/bin/env python3
"""Validate operator inputs without printing secrets. Run from repository root."""

import json
import re
import sys
from pathlib import Path

env_path = Path(".env")
if not env_path.is_file():
    print(
        "Create .env first: copy .env.example to .env, then replace every placeholder."
    )
    sys.exit(2)

values: dict[str, str] = {}
for line in env_path.read_text().splitlines():
    if line.strip() and not line.lstrip().startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

errors: list[str] = []
for key in ("CATALOG_HOST", "ACME_EMAIL", "FUSEKI_PASSWORD", "EDC_DEMO_PARTICIPANTS"):
    value = values.get(key, "")
    if not value or "REPLACE" in value or "example.org" in value:
        errors.append(f"{key}: replace the placeholder")

hostname = values.get("CATALOG_HOST", "")
if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", hostname):
    errors.append("CATALOG_HOST: use a DNS hostname without a protocol, port or path")

if values.get("CATALOG_MODE") != "http-demo":
    errors.append("CATALOG_MODE: use http-demo")

public_url = values.get("CATALOG_PUBLIC_URL", "")
if public_url and public_url != f"https://{hostname}":
    errors.append("CATALOG_PUBLIC_URL: use https:// followed by CATALOG_HOST")

password = values.get("FUSEKI_PASSWORD", "")
if not re.fullmatch(r"[a-fA-F0-9]{48,}", password):
    errors.append(
        "FUSEKI_PASSWORD: use at least 24 random bytes encoded as hexadecimal"
    )

try:
    participants = json.loads(values.get("EDC_DEMO_PARTICIPANTS", ""))
except json.JSONDecodeError:
    participants = None
    errors.append(
        "EDC_DEMO_PARTICIPANTS: use a JSON object of participant IDs to tokens"
    )

if isinstance(participants, dict):
    if len(participants) < 2:
        errors.append("EDC_DEMO_PARTICIPANTS: configure at least two participants")
    tokens: list[str] = []
    for participant_id, token in participants.items():
        if not isinstance(participant_id, str) or ":" not in participant_id:
            errors.append("EDC_DEMO_PARTICIPANTS: each participant ID must be a URI")
        if not isinstance(token, str) or not re.fullmatch(r"[a-fA-F0-9]{64,}", token):
            errors.append(
                "EDC_DEMO_PARTICIPANTS: each token needs at least 32 random bytes in hexadecimal"
            )
        elif token in tokens:
            errors.append(
                "EDC_DEMO_PARTICIPANTS: each participant needs a different token"
            )
        else:
            tokens.append(token)
elif participants is not None:
    errors.append("EDC_DEMO_PARTICIPANTS: use a JSON object")

for key in (
    "CATALOG_MAX_INGEST_BYTES",
    "SPARQL_MAX_REQUEST_BYTES",
    "SPARQL_MAX_ROWS",
    "SPARQL_MAX_RESPONSE_BYTES",
):
    value = values.get(key)
    if value:
        try:
            if int(value) <= 0:
                raise ValueError
        except ValueError:
            errors.append(f"{key}: use a positive integer")

for key in (
    "CATALOG_STARTUP_WAIT_SECONDS",
    "FUSEKI_TIMEOUT_SECONDS",
    "SPARQL_TIMEOUT_SECONDS",
):
    value = values.get(key)
    if value:
        try:
            if float(value) <= 0:
                raise ValueError
        except ValueError:
            errors.append(f"{key}: use a positive number")

if errors:
    print("\n".join(errors))
    sys.exit(1)

print(
    "Configuration fields look ready. DNS and network reachability still need live checks."
)
