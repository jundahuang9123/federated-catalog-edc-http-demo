from __future__ import annotations

import re

from rdflib import DCTERMS, RDF, Graph, Namespace

from core.interfaces.store import CatalogStore
from core.shared.participant_graph import participant_from_graph_uri

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
        if "COUNT(DISTINCT ?dataset)" in sparql:
            datasets = set()
            graphs_with_datasets = set()
            for graph_id, rdf_payload in self.graphs.items():
                graph = Graph().parse(data=rdf_payload, format="turtle")
                for dataset in graph.subjects(RDF.type, DCAT.Dataset):
                    datasets.add(str(dataset))
                    graphs_with_datasets.add(graph_id)
            return [
                {
                    "dataset_count": str(len(datasets)),
                    "graph_count": str(len(graphs_with_datasets)),
                }
            ]

        detail_match = re.search(r"BIND\(<([^>]+)> AS \?dataset\)", sparql)
        if detail_match:
            dataset_id = detail_match.group(1)
            rows: list[dict[str, object]] = []
            for graph_id, rdf_payload in self.graphs.items():
                graph = Graph().parse(data=rdf_payload, format="turtle")
                dataset = next(
                    (
                        subject
                        for subject in graph.subjects(RDF.type, DCAT.Dataset)
                        if str(subject) == dataset_id
                    ),
                    None,
                )
                if dataset is None:
                    continue
                title = next(graph.objects(dataset, DCTERMS.title), None)
                subjects = {dataset}
                subjects.update(graph.objects(dataset, DCAT.distribution))
                for subject in subjects:
                    for predicate, obj in graph.predicate_objects(subject):
                        rows.append(
                            {
                                "graph": graph_id,
                                "s": str(subject),
                                "p": str(predicate),
                                "o": str(obj),
                                "title": str(title) if title else None,
                                "type": str(DCAT.Dataset),
                                "provider": participant_from_graph_uri(graph_id),
                            }
                        )
            return rows

        rows: list[dict[str, object]] = []
        for graph_id, rdf_payload in self.graphs.items():
            graph = Graph().parse(data=rdf_payload, format="turtle")
            for dataset in graph.subjects(RDF.type, DCAT.Dataset):
                title = next(graph.objects(dataset, DCTERMS.title), None)
                rows.append(
                    {
                        "graph": graph_id,
                        "dataset": str(dataset),
                        "title": str(title) if title else None,
                        "provider": participant_from_graph_uri(graph_id),
                    }
                )
        return rows
