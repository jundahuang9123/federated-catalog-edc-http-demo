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

    def _catalog_metadata(self, graph: str | None = None) -> dict:
        graph_filter = f"VALUES ?graph {{ {_sparql_iri(graph)} }}" if graph else ""
        rows = self.store.query(f"""
            PREFIX dcat: <http://www.w3.org/ns/dcat#>
            PREFIX dct: <http://purl.org/dc/terms/>
            PREFIX edc: <https://w3id.org/edc/v0.0.1/ns/>
            SELECT DISTINCT ?graph ?catalog ?did ?endpoint ?parent ?member ?label ?series
            WHERE {{
              {graph_filter}
              GRAPH ?graph {{
                ?catalog a dcat:Catalog .
                OPTIONAL {{ ?catalog edc:participantId ?did . FILTER(STRSTARTS(STR(?did), "did:")) }}
                OPTIONAL {{
                  ?catalog dcat:service ?service .
                  ?service dcat:endpointDescription "dspace:connector" ; dcat:endpointURL ?endpoint .
                }}
                OPTIONAL {{
                  {{ ?catalog dcat:dataset ?member . BIND(?catalog AS ?parent) }}
                  UNION {{
                    ?catalog dcat:dataset/dcat:seriesMember* ?parent .
                    ?parent dcat:seriesMember ?member .
                  }}
                  OPTIONAL {{ ?member dct:title ?label }}
                  OPTIONAL {{ ?member a dcat:DatasetSeries . BIND(true AS ?series) }}
                }}
              }}
            }} ORDER BY STR(?graph) STR(?catalog) COALESCE(STR(?did), "") COALESCE(STR(?endpoint), "") COALESCE(STR(?member), "") COALESCE(STR(?label), "")
        """)
        results = {}
        for row in rows:
            key = (str(row["graph"]), str(row["catalog"]))
            metadata = results.setdefault(
                key, {"provider_did": None, "dsp_endpoint": None, "hierarchy": []}
            )
            for source, target in (("did", "provider_did"), ("endpoint", "dsp_endpoint")):
                if row.get(source) and metadata[target] is None:
                    metadata[target] = str(row[source])
            if row.get("member"):
                node = {
                    "id": str(row["member"]),
                    "parent_id": str(row["parent"]),
                    "title": str(row.get("label") or ""),
                    "kind": "series" if str(row.get("series")) == "true" else "dataset",
                }
                if not any(
                    n["id"] == node["id"] and n["parent_id"] == node["parent_id"]
                    for n in metadata["hierarchy"]
                ):
                    metadata["hierarchy"].append(node)
        return results

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
        metadata = self._catalog_metadata()
        return [
            CatalogResult(
                catalog_id=str(row["catalog"]),
                provider=participant_from_graph_uri(str(row["graph"])),
                graph=str(row["graph"]),
                title=str(row.get("title") or "") or None,
                dataset_count=_int_value(row.get("count")),
                metadata=metadata.get((str(row["graph"]), str(row["catalog"])), {}),
            )
            for row in rows
        ]

    def list_datasets(self) -> list[DatasetResult]:
        rows = self.store.query(
            """
            PREFIX dcat: <http://www.w3.org/ns/dcat#>
            PREFIX dct: <http://purl.org/dc/terms/>
            PREFIX edc: <https://w3id.org/edc/v0.0.1/ns/>

            SELECT DISTINCT ?graph ?catalog ?dataset ?title ?description ?keyword ?asset
            WHERE {
              GRAPH ?graph {
                ?catalog a dcat:Catalog ; dcat:dataset/dcat:seriesMember* ?dataset .
                ?dataset a dcat:Dataset .
                OPTIONAL { ?dataset dct:title ?title . }
                OPTIONAL { ?dataset dct:description ?description . }
                OPTIONAL { ?dataset dcat:keyword ?keyword . }
                OPTIONAL { ?dataset dct:identifier ?standardId }
                OPTIONAL { ?dataset edc:id ?edcId }
                BIND(COALESCE(?edcId, ?standardId) AS ?asset)
              }
            }
            ORDER BY LCASE(STR(?title)) STR(?dataset) COALESCE(STR(?asset), "")
            """
        )
        # One listing per source and dataset, even with multilingual/repeated literals.
        catalog_metadata = self._catalog_metadata()
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
                        "asset_id": str(row.get("asset") or "") or None,
                        **{
                            k: v
                            for k, v in catalog_metadata.get(
                                (graph, str(row.get("catalog") or "")), {}
                            ).items()
                            if k != "hierarchy"
                        },
                    },
                )
            terms = items[key].metadata["search_terms"]
            for field in ("title", "description", "keyword", "asset"):
                value = str(row.get(field) or "")
                if value and value not in terms:
                    terms.append(value)
        for item in items.values():
            for field in ("provider_did", "dsp_endpoint"):
                if item.metadata.get(field):
                    item.metadata["search_terms"].append(item.metadata[field])
        return list(items.values())

    def get_dataset(self, dataset_id: str, graph: str | None = None) -> DatasetDetail | None:
        dataset_iri = _sparql_iri(dataset_id)
        graph_filter = f"VALUES ?graph {{ {_sparql_iri(graph)} }}" if graph is not None else ""
        rows = self.store.query(
            f"""
            PREFIX dcat: <http://www.w3.org/ns/dcat#>
            PREFIX dct: <http://purl.org/dc/terms/>

            SELECT DISTINCT ?graph ?catalog ?s ?p ?o ?title ?type ?objectKind ?subjectKind ?datatype ?language
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
                UNION {{
                  ?dataset <https://w3id.org/construct-dcat#hasAASSubmodel> ?s .
                  ?s ?p ?o .
                }}
                UNION {{
                  ?catalog dcat:dataset ?o . ?o dcat:seriesMember* ?dataset .
                  BIND(?catalog AS ?s) BIND(dcat:dataset AS ?p)
                }}
                UNION {{
                  ?catalog dcat:dataset/dcat:seriesMember* ?s .
                  ?s dcat:seriesMember ?o . ?o dcat:seriesMember* ?dataset .
                  BIND(dcat:seriesMember AS ?p)
                }}
                BIND(IF(isLiteral(?o), "literal", IF(isBlank(?o), "bnode", "uri")) AS ?objectKind)
                BIND(IF(isBlank(?s), "bnode", "uri") AS ?subjectKind)
                BIND(IF(isLiteral(?o), STR(datatype(?o)), "") AS ?datatype)
                BIND(IF(isLiteral(?o), lang(?o), "") AS ?language)
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
        triples = sorted(
            {
                RdfTriple(
                    subject=str(row["s"]),
                    predicate=str(row["p"]),
                    object=str(row["o"]),
                    object_type=str(row.get("objectKind") or "uri"),
                    subject_type=str(row.get("subjectKind") or "uri"),
                    datatype=str(row.get("datatype") or "") or None,
                    language=str(row.get("language") or "") or None,
                )
                for row in rows
                if row.get("s") is not None
                and row.get("p") is not None
                and row.get("o") is not None
            },
            key=lambda t: (t.subject, t.predicate, t.object, t.language or "", t.datatype or ""),
        )
        catalog_id = str(rows[0].get("catalog") or "")
        connector = self._catalog_metadata(graph).get((graph, catalog_id), {})
        identifiers = {
            t.predicate: t.object
            for t in reversed(triples)
            if t.subject == dataset_id
            and t.predicate
            in {"https://w3id.org/edc/v0.0.1/ns/id", "http://purl.org/dc/terms/identifier"}
        }
        return DatasetDetail(
            dataset_id=dataset_id,
            title=str(rows[0]["title"]) if rows[0].get("title") else None,
            type="dcat:Dataset",
            provider=participant_from_graph_uri(graph),
            metadata={
                "graph": graph,
                "mode": "http-demo",
                "catalog_id": catalog_id,
                "provider_did": connector.get("provider_did"),
                "dsp_endpoint": connector.get("dsp_endpoint"),
                "asset_id": identifiers.get("https://w3id.org/edc/v0.0.1/ns/id")
                or identifiers.get("http://purl.org/dc/terms/identifier"),
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
