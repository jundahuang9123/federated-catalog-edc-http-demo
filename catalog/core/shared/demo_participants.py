"""Parse the participant/token mapping used by the HTTP adapter simulator."""

from __future__ import annotations

import json
from collections.abc import Mapping


class ParticipantConfigurationError(ValueError):
    pass


def parse_demo_participants(raw_value: str) -> dict[str, str]:
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ParticipantConfigurationError(
            "EDC_DEMO_PARTICIPANTS must be a JSON object of participant IDs to tokens"
        ) from exc

    if not isinstance(payload, Mapping) or not payload:
        raise ParticipantConfigurationError(
            "EDC_DEMO_PARTICIPANTS must contain at least one participant"
        )

    participants: dict[str, str] = {}
    seen_tokens: set[str] = set()
    for raw_participant_id, raw_token in payload.items():
        if not isinstance(raw_participant_id, str) or not isinstance(raw_token, str):
            raise ParticipantConfigurationError("Participant IDs and tokens must be strings")
        participant_id = raw_participant_id.strip()
        token = raw_token.strip()
        if (
            not participant_id
            or ":" not in participant_id
            or any(char.isspace() for char in participant_id)
        ):
            raise ParticipantConfigurationError(
                "Each participant ID must be a non-empty URI without whitespace"
            )
        if not token or not token.isascii():
            raise ParticipantConfigurationError(
                "Participant tokens must be non-empty ASCII strings"
            )
        if token in seen_tokens:
            raise ParticipantConfigurationError("Each participant must use a different token")
        participants[participant_id] = token
        seen_tokens.add(token)

    return participants
