"""Fuseki-backed catalog store for the HTTP ingestion demo."""

from core.interfaces.store import CatalogStore
from core.shared.fuseki import FusekiClient


class HttpDemoStore(CatalogStore):
    def __init__(self, fuseki: FusekiClient | None = None) -> None:
        self.fuseki = fuseki or FusekiClient()

    def replace_graph(self, graph_id: str, rdf_payload: str) -> None:
        self.fuseki.replace_named_graph(graph_id, rdf_payload, content_type="text/turtle")

    def query(self, sparql: str) -> list[dict[str, object]]:
        return self.fuseki.query(sparql)
