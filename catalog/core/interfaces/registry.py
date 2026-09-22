from abc import ABC, abstractmethod


class RegistryCheck(ABC):
    """Verify membership in the configured demo participant directory."""

    @abstractmethod
    def is_member(self, participant_id: str) -> bool:
        raise NotImplementedError
