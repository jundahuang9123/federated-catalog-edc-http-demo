"""Bearer-token authentication for the simulated EDC HTTP delivery boundary."""

from dataclasses import dataclass

from fastapi import Request

from modes.http_demo.registry import DemoParticipantRegistry


class HttpDemoAuthError(RuntimeError):
    def __init__(self, error: str, detail: str, status_code: int = 401) -> None:
        super().__init__(detail)
        self.error = error
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class AuthenticatedDemoParticipant:
    participant_id: str
    auth_mode: str = "demo-bearer"


@dataclass(frozen=True)
class HttpDemoTokenAuth:
    registry: DemoParticipantRegistry

    def authenticate(self, request: Request) -> AuthenticatedDemoParticipant:
        authorization = request.headers.get("authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token.strip():
            raise HttpDemoAuthError(
                "invalid_credentials",
                "A valid simulator bearer token is required",
            )

        participant_id = self.registry.participant_for_token(token.strip())
        if participant_id is None:
            raise HttpDemoAuthError(
                "invalid_credentials",
                "A valid simulator bearer token is required",
            )
        return AuthenticatedDemoParticipant(participant_id=participant_id)
