"""Discovery over metadata delivered through the simulated EDC HTTP boundary."""

from __future__ import annotations

import re

from core.interfaces.discovery import (
    AmbiguousDatasetError,
    CatalogResult,
    CatalogStatus,
    DatasetDetail,
    DatasetResult,
    DiscoveryService,
    InvalidDatasetIdError,
    RdfTriple,
)
from core.interfaces.store import CatalogStore
from core.shared.participant_graph import participant_from_graph_uri
from modes.http_demo.registry import DemoParticipantRegistry


def _int_value(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


_IRI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_FORBIDDEN_IRI_CHARACTERS = frozenset('<>"{}|^`\\')


def _sparql_iri(value: str) -> str:
    if (
        not value
        or len(value) > 2048
        or not _IRI_SCHEME.match(value)
        or any(ord(character) <= 0x20 for character in value)
        or any(character in _FORBIDDEN_IRI_CHARACTERS for character in value)
    ):
        raise InvalidDatasetIdError("dataset_id must be a safe absolute IRI")
    return f"<{value}>"


class HttpDemoDiscovery(DiscoveryService):
    def __init__(self, store: CatalogStore, registry: DemoParticipantRegistry) -> None:
        self.store = store
        self.registry = registry

    def list_catalogs(self) -> list[CatalogResult]:
        rows = self.store.query("""
            PREFIX dcat: <http://www.w3.org/ns/dcat#>
            PREFIX dct: <http://purl.org/dc/terms/>
            SELECT ?graph ?catalog (MIN(COALESCE(STR(?label), "")) AS ?title)
                   (COUNT(DISTINCT ?dataset) AS ?count)
            WHERE {
              GRAPH ?graph {
                ?catalog a dcat:Catalog .
                OPTIONAL { ?catalog dct:title ?label }
                OPTIONAL {
                  ?catalog dcat:dataset/dcat:seriesMember* ?dataset .
                  ?dataset a dcat:Dataset .
                }
              }
            } GROUP BY ?graph ?catalog ORDER BY STR(?catalog) STR(?graph)
        """)
        return [
            CatalogResult(
                catalog_id=str(row["catalog"]),
                provider=participant_from_graph_uri(str(row["graph"])),
                graph=str(row["graph"]),
                title=str(row.get("title") or "") or None,
                dataset_count=_int_value(row.get("count")),
            )
            for row in rows
        ]

    def list_datasets(self) -> list[DatasetResult]:
        rows = self.store.query(
            """
            PREFIX dcat: <http://www.w3.org/ns/dcat#>
            PREFIX dct: <http://purl.org/dc/terms/>

            SELECT DISTINCT ?graph ?catalog ?dataset ?title ?description ?keyword
            WHERE {
              GRAPH ?graph {
                ?catalog a dcat:Catalog ; dcat:dataset/dcat:seriesMember* ?dataset .
                ?dataset a dcat:Dataset .
                OPTIONAL { ?dataset dct:title ?title . }
                OPTIONAL { ?dataset dct:description ?description . }
                OPTIONAL { ?dataset dcat:keyword ?keyword . }
              }
            }
            ORDER BY LCASE(STR(?title)) STR(?dataset)
            """
        )
        # One listing per source and dataset, even with multilingual/repeated literals.
        items = {}
        for row in rows:
            graph, dataset = str(row.get("graph") or ""), str(row.get("dataset") or "")
            key = (graph, dataset)
            if key not in items:
                items[key] = DatasetResult(
                    dataset_id=dataset,
                    title=str(row.get("title") or "") or None,
                    type="dcat:Dataset",
                    provider=participant_from_graph_uri(graph),
                    metadata={
                        "graph": graph,
                        "catalog_id": str(row.get("catalog") or ""),
                        "mode": "http-demo",
                        "search_terms": [],
                    },
                )
            terms = items[key].metadata["search_terms"]
            for field in ("title", "description", "keyword"):
                value = str(row.get(field) or "")
                if value and value not in terms:
                    terms.append(value)
        return list(items.values())

    def get_dataset(self, dataset_id: str, graph: str | None = None) -> DatasetDetail | None:
        dataset_iri = _sparql_iri(dataset_id)
        graph_filter = f"VALUES ?graph {{ {_sparql_iri(graph)} }}" if graph is not None else ""
        rows = self.store.query(
            f"""
            PREFIX dcat: <http://www.w3.org/ns/dcat#>
            PREFIX dct: <http://purl.org/dc/terms/>

            SELECT DISTINCT ?graph ?catalog ?s ?p ?o ?title ?type
            WHERE {{
              {graph_filter}
              GRAPH ?graph {{
                BIND({dataset_iri} AS ?dataset)
                ?catalog a dcat:Catalog ; dcat:dataset/dcat:seriesMember* ?dataset .
                ?dataset a dcat:Dataset .
                OPTIONAL {{ ?dataset dct:title ?title . }}
                OPTIONAL {{ ?dataset a ?type . }}
                {{
                  ?dataset ?p ?o .
                  BIND(?dataset AS ?s)
                }}
                UNION
                {{
                  ?dataset dcat:distribution ?s .
                  ?s ?p ?o .
                }}
              }}
            }}
            ORDER BY STR(?s) STR(?p) STR(?o)
            """
        )
        if not rows:
            return None

        if len({str(row.get("graph")) for row in rows}) > 1:
            raise AmbiguousDatasetError("Dataset occurs in multiple catalogs; supply its graph")
        graph = str(rows[0].get("graph") or "")
        types = sorted({str(row["type"]) for row in rows if row.get("type")})
        triples = [
            RdfTriple(
                subject=str(row.get("s") or ""),
                predicate=str(row.get("p") or ""),
                object=str(row.get("o") or ""),
            )
            for row in rows
            if row.get("s") and row.get("p") and row.get("o")
        ]
        return DatasetDetail(
            dataset_id=dataset_id,
            title=str(rows[0]["title"]) if rows[0].get("title") else None,
            type="dcat:Dataset",
            provider=participant_from_graph_uri(graph),
            metadata={
                "graph": graph,
                "mode": "http-demo",
                "catalog_id": str(rows[0].get("catalog") or ""),
            },
            types=types,
            triples=triples,
        )

    def get_status(self) -> CatalogStatus:
        try:
            rows = self.store.query(
                """
                PREFIX dcat: <http://www.w3.org/ns/dcat#>

                SELECT
                  (COUNT(?dataset) AS ?dataset_count)
                  (COUNT(DISTINCT ?graph) AS ?graph_count)
                WHERE {
                  { SELECT DISTINCT ?graph ?dataset WHERE {
                    GRAPH ?graph {
                      ?catalog a dcat:Catalog .
                      OPTIONAL {
                        ?catalog dcat:dataset/dcat:seriesMember* ?dataset .
                        ?dataset a dcat:Dataset .
                      }
                    }
                  } }
                }
                """
            )
            first = rows[0] if rows else {}
            return CatalogStatus(
                mode="http-demo",
                operational=True,
                dataset_count=_int_value(first.get("dataset_count")),
                graph_count=_int_value(first.get("graph_count")),
                participant_count=len(self.registry.participants),
                dependencies={"fuseki": True, "participant_config": True},
            )
        except Exception as exc:  # noqa: BLE001 - readiness must contain store adapter failures
            return CatalogStatus(
                mode="http-demo",
                operational=False,
                participant_count=len(self.registry.participants),
                detail=f"Catalog discovery unavailable: {exc}",
                dependencies={"fuseki": False, "participant_config": True},
            )
