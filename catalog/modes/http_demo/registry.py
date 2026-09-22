"""Configured participant directory for the EDC HTTP adapter simulator."""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

from core.interfaces.registry import RegistryCheck
from core.shared.demo_participants import parse_demo_participants


@dataclass(frozen=True)
class DemoParticipantRegistry(RegistryCheck):
    participants: dict[str, str]

    @classmethod
    def from_env(cls) -> DemoParticipantRegistry:
        return cls(parse_demo_participants(os.getenv("EDC_DEMO_PARTICIPANTS", "")))

    def is_member(self, participant_id: str) -> bool:
        return participant_id in self.participants

    def participant_for_token(self, candidate: str) -> str | None:
        matched_participant: str | None = None
        candidate_bytes = candidate.encode("utf-8")
        for participant_id, configured_token in self.participants.items():
            if hmac.compare_digest(candidate_bytes, configured_token.encode("ascii")):
                matched_participant = participant_id
        return matched_participant
