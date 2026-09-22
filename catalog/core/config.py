import os
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol

from core.interfaces.discovery import DiscoveryService
from core.interfaces.ingest import IngestSource
from core.interfaces.registry import RegistryCheck
from core.interfaces.store import CatalogStore
from core.interfaces.validation import ValidationGate


class ModeRegistration(Protocol):
    name: str
    registry: RegistryCheck
    validation: ValidationGate
    store: CatalogStore
    ingest: IngestSource
    discovery: DiscoveryService


@dataclass(frozen=True)
class CatalogSettings:
    mode: str


def get_settings() -> CatalogSettings:
    return CatalogSettings(mode=os.getenv("CATALOG_MODE", "http-demo").strip().lower())


def load_active_mode() -> ModeRegistration:
    settings = get_settings()
    if settings.mode != "http-demo":
        raise RuntimeError("CATALOG_MODE must be set to 'http-demo'")

    module = import_module("modes.http_demo")
    return module.register()
