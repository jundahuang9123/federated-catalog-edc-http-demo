from __future__ import annotations

from rdflib import Dataset, Namespace, URIRef

from core.interfaces.store import CatalogStore

DCAT = Namespace("http://www.w3.org/ns/dcat#")


VALID_TURTLE = """
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct: <http://purl.org/dc/terms/> .

<https://example.org/catalogs/test> a dcat:Catalog ;
    dcat:contactPoint <https://example.org/profile/card#me> ;
    dcat:dataset <https://example.org/datasets/test> .

<https://example.org/datasets/test> a dcat:Dataset ;
    dct:title "Test dataset" ;
    dcat:contactPoint <https://example.org/profile/card#me> ;
    dcat:distribution <https://example.org/datasets/test/distribution> .

<https://example.org/datasets/test/distribution> a dcat:Distribution ;
    dcat:downloadURL <https://example.org/data/test.csv> ;
    dcat:mediaType "text/csv" .
"""

VALID_TURTLE_REPLACEMENT = VALID_TURTLE.replace("Test dataset", "Replacement dataset")

INVALID_SHACL_TURTLE = """
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dct: <http://purl.org/dc/terms/> .

<https://example.org/catalogs/test> a dcat:Catalog ;
    dcat:contactPoint <https://example.org/profile/card#me> ;
    dcat:dataset <https://example.org/datasets/test> .

<https://example.org/datasets/test> a dcat:Dataset ;
    dct:title "Missing distribution" ;
    dcat:contactPoint <https://example.org/profile/card#me> .
"""


class MemoryCatalogStore(CatalogStore):
    def __init__(self) -> None:
        self.graphs: dict[str, str] = {}

    def replace_graph(self, graph_id: str, rdf_payload: str) -> None:
        self.graphs[graph_id] = rdf_payload

    def query(self, sparql: str) -> list[dict[str, object]]:
        dataset = Dataset()
        for graph_id, payload in self.graphs.items():
            dataset.graph(URIRef(graph_id)).parse(data=payload, format="turtle")
        return [
            {str(key): str(value) for key, value in row.asdict().items()}
            for row in dataset.query(sparql)
        ]
