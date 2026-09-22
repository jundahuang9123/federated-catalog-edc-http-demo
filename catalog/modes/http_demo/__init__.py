from dataclasses import dataclass

from core.interfaces.discovery import DiscoveryService
from core.interfaces.ingest import IngestSource
from core.interfaces.registry import RegistryCheck
from core.interfaces.store import CatalogStore
from core.interfaces.validation import ValidationGate
from core.shared.shacl_validate import ShaclValidationGate
from modes.http_demo.auth import HttpDemoTokenAuth
from modes.http_demo.discovery import HttpDemoDiscovery
from modes.http_demo.ingest import HttpDemoIngest
from modes.http_demo.registry import DemoParticipantRegistry
from modes.http_demo.store import HttpDemoStore


@dataclass(frozen=True)
class HttpDemoMode:
    registry: RegistryCheck
    validation: ValidationGate
    store: CatalogStore
    ingest: IngestSource
    discovery: DiscoveryService
    name: str = "http-demo"


def register() -> HttpDemoMode:
    registry = DemoParticipantRegistry.from_env()
    validation = ShaclValidationGate()
    store = HttpDemoStore()
    auth = HttpDemoTokenAuth(registry)
    ingest = HttpDemoIngest(validation=validation, store=store, auth=auth)
    discovery = HttpDemoDiscovery(store=store, registry=registry)
    return HttpDemoMode(
        registry=registry,
        validation=validation,
        store=store,
        ingest=ingest,
        discovery=discovery,
    )
