"""End-to-end behavior with an in-memory transport standing in for Fuseki."""

import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient
from rdflib import Dataset, Graph, URIRef
from rdflib.compare import isomorphic

from core.shared.fuseki import FusekiClient, FusekiSettings
from core.shared.participant_graph import graph_uri_for_participant
from core.shared.shacl_validate import ShaclValidationGate
from modes.http_demo.auth import HttpDemoTokenAuth
from modes.http_demo.discovery import HttpDemoDiscovery
from modes.http_demo.ingest import HttpDemoIngest
from modes.http_demo.registry import DemoParticipantRegistry
from modes.http_demo.store import HttpDemoStore

DATA = Path(__file__).resolve().parents[2] / "demo-data"
A = "urn:demo:participant:a"
B = "urn:demo:participant:b"
TOKEN_A = "a" * 64
TOKEN_B = "b" * 64
C = "urn:demo:participant:c"
TOKEN_C = "c" * 64


@pytest.fixture
def system(monkeypatch):
    monkeypatch.setenv("CATALOG_MODE", "http-demo")
    monkeypatch.setenv("EDC_DEMO_PARTICIPANTS", json.dumps({A: TOKEN_A, B: TOKEN_B, C: TOKEN_C}))
    monkeypatch.setenv("CATALOG_STARTUP_CHECKS", "false")
    monkeypatch.delenv("CATALOG_PUBLIC_URL", raising=False)
    dataset = Dataset()
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "PUT":
            graph = URIRef(request.url.params["graph"])
            replacement = Graph().parse(data=request.content, format="turtle")
            dataset.graph(graph).remove((None, None, None))
            for triple in replacement:
                dataset.graph(graph).add(triple)
            return httpx.Response(204)
        query = parse_qs(request.content.decode())["query"][0]
        result = dataset.query(query)
        return httpx.Response(200, content=result.serialize(format="json"))

    fuseki = FusekiClient(
        FusekiSettings("http://index/catalog"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    store = HttpDemoStore(fuseki)
    registry = DemoParticipantRegistry({A: TOKEN_A, B: TOKEN_B, C: TOKEN_C})
    mode = SimpleNamespace(
        name="http-demo",
        store=store,
        discovery=HttpDemoDiscovery(store, registry),
        ingest=HttpDemoIngest(ShaclValidationGate(), store, HttpDemoTokenAuth(registry)),
    )
    from core import app as module

    monkeypatch.setattr(module, "load_active_mode", lambda: mode)
    with TestClient(module.create_app()) as client:
        yield client, dataset, calls


def publish(client, token, path):
    return client.post(
        "/catalog",
        content=(DATA / path).read_bytes(),
        headers={"Content-Type": "text/turtle", "Authorization": f"Bearer {token}"},
    )


def test_live_update_validation_discovery_and_semantic_query(system):
    client, index, calls = system
    assert publish(client, TOKEN_A, "participant-a/catalog-v1.ttl").status_code == 200
    assert publish(client, TOKEN_B, "participant-b/catalog-v1.ttl").status_code == 200
    b_before = Graph()
    for triple in index.graph(URIRef(graph_uri_for_participant(B))):
        b_before.add(triple)
    model = index.graph(URIRef("urn:model:demo:reserved"))
    model.add((URIRef("urn:entity"), URIRef("urn:property"), URIRef("urn:value")))
    wall_query = (DATA / "queries/walls.rq").read_text()
    assert (
        len(client.post("/sparql", json={"query": wall_query}).json()["results"]["bindings"]) == 2
    )
    assert len(client.get("/datasets").json()) == 3
    detail = client.get(
        "/datasets/detail", params={"dataset_id": "https://example.org/live-demo/a-frame"}
    )
    assert detail.status_code == 200
    assert detail.json()["provider"] == A

    assert publish(client, TOKEN_A, "participant-a/catalog-v2.ttl").status_code == 200
    rows = client.get("/datasets").json()
    assert len(rows) == 3
    assert not any(row["dataset_id"].endswith("a-slabs") for row in rows)
    assert any(row["title"] == "Frame export — revision 2" for row in rows)
    assert isomorphic(b_before, index.graph(URIRef(graph_uri_for_participant(B))))
    assert len(model) == 1
    assert (
        len(client.post("/sparql", json={"query": wall_query}).json()["results"]["bindings"]) == 3
    )

    a_before = set(index.graph(URIRef(graph_uri_for_participant(A))))
    invalid = publish(client, TOKEN_A, "invalid/invalid-catalog.ttl")
    assert invalid.status_code == 422 and invalid.json()["stage"] == "validation"
    assert set(index.graph(URIRef(graph_uri_for_participant(A)))) == a_before
    assert publish(client, "wrong-token", "participant-b/catalog-v1.ttl").status_code == 401
    assert all(request.method != "DELETE" for request in calls)


@pytest.mark.parametrize(
    "query",
    [
        "INSERT DATA { <urn:s> <urn:p> <urn:o> }",
        "DELETE WHERE { ?s ?p ?o }",
        "DROP ALL",
        "LOAD <http://example.org/file>",
        "CLEAR ALL",
        "CREATE GRAPH <urn:g>",
        "MOVE DEFAULT TO GRAPH <urn:g>",
        "COPY DEFAULT TO GRAPH <urn:g>",
        "ADD DEFAULT TO GRAPH <urn:g>",
        "SELECT * WHERE { SERVICE <http://localhost:3030/> { ?s ?p ?o } }",
        "SELECT * WHERE { { SELECT * WHERE { SERVICE SILENT <http://example.org> { ?s ?p ?o } } } }",
        "SELECT * FROM <http://example.org/a> WHERE { ?s ?p ?o }",
        'SELECT (<http://example.org/function>("x") AS ?x) WHERE {}',
        "SELECT ???",
        "PREFIX bad: <urn:bad> SELECT ?s WHERE { ?s unknown:p ?o }",
        "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }",
    ],
)
def test_unsafe_or_malformed_queries_never_reach_fuseki(system, query):
    client, _, calls = system
    before = len(calls)
    assert client.post("/sparql", json={"query": query}).status_code == 400
    assert len(calls) == before


def test_query_json_terms_ask_and_limits(system):
    client, _, _ = system
    response = client.post(
        "/sparql", json={"query": 'SELECT ("bonjour"@fr AS ?label) (42 AS ?n) WHERE {}'}
    )
    assert response.status_code == 200
    binding = response.json()["results"]["bindings"][0]
    assert binding["label"]["xml:lang"] == "fr"
    assert binding["n"]["datatype"].endswith("#integer")
    assert (
        client.post("/sparql", json={"query": "ASK { GRAPH <urn:missing> { ?s ?p ?o } }"}).json()[
            "boolean"
        ]
        is False
    )
    assert client.post("/sparql", json={"query": "ASK {}"}).json()["boolean"] is True
    values = " ".join(str(number) for number in range(600))
    rows = client.post(
        "/sparql", json={"query": f"SELECT ?n WHERE {{ VALUES ?n {{ {values} }} }}"}
    ).json()["results"]["bindings"]
    assert len(rows) == 500
    assert client.post("/sparql", content=b"x" * 32769).status_code == 413
    assert client.post("/sparql", content=b"not JSON").status_code == 400
    assert client.post("/sparql", json={"query": 5}).status_code == 400


def test_literal_update_word_is_not_rejected(system):
    client, _, _ = system
    query = '# SELECT\nPREFIX ex: <urn:SELECT>\nSELECT ("DELETE SERVICE" AS ?text) WHERE {}'
    assert client.post("/sparql", json={"query": query}).status_code == 200


@pytest.mark.parametrize(
    "dataset_id",
    [
        "relative-id",
        "urn:test\\u003E . ?s ?p ?o",
        'urn:test"> <urn:other>',
        "urn:test{unsafe}",
    ],
)
def test_unsafe_dataset_id_never_reaches_fuseki(system, dataset_id):
    client, _, calls = system
    before = len(calls)

    response = client.get("/datasets/detail", params={"dataset_id": dataset_id})

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_dataset_id"
    assert len(calls) == before


def test_failed_put_does_not_send_delete():
    calls = []

    def handler(request):
        calls.append(request.method)
        return httpx.Response(500)

    client = FusekiClient(
        FusekiSettings("http://index/catalog"),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(RuntimeError):
        client.replace_named_graph("urn:catalog:a", "<urn:s> <urn:p> <urn:o> .")
    assert calls == ["PUT"]


@pytest.mark.parametrize(
    "kind,expected",
    [("timeout", 504), ("network", 502), ("oversize", 502), ("syntax", 400)],
)
def test_query_backend_failures_are_controlled(system, monkeypatch, kind, expected):
    client, _, _ = system

    def fail(*args, **kwargs):
        if kind == "timeout":
            raise httpx.ReadTimeout("timeout")
        if kind == "network":
            raise httpx.ConnectError("unavailable")
        if kind == "syntax":
            response = httpx.Response(400, request=httpx.Request("POST", "http://index/query"))
            response.raise_for_status()
        raise ValueError("Response limit exceeded")

    monkeypatch.setattr(FusekiClient, "query_results", fail)
    assert client.post("/sparql", json={"query": "ASK {}"}).status_code == expected
    assert client.post("/sparql", json={"query": "ASK {}"}).status_code == expected


def test_one_catalog_per_publisher_and_search_across_sources(system):
    client, index, _ = system
    assert publish(client, TOKEN_A, "participant-a/catalog-v1.ttl").status_code == 200
    assert publish(client, TOKEN_B, "participant-b/catalog-v1.ttl").status_code == 200
    catalogs = client.get("/catalogs").json()
    assert len(catalogs) == 2
    assert {row["provider"] for row in catalogs} == {A, B}
    assert sum(row["dataset_count"] for row in catalogs) == 3
    assert {
        row["provider"] for row in client.get("/datasets", params={"q": "live-demo"}).json()
    } == {A, B}
    rows = client.get("/datasets", params={"q": "FRAME"}).json()
    assert len(rows) == 1 and rows[0]["provider"] == A
    assert rows[0]["metadata"]["catalog_id"].endswith("a-catalog")
    assert client.get("/datasets", params={"q": '" } UNION { ?s ?p ?o } #'}).json() == []

    before = set(index.graph(URIRef(graph_uri_for_participant(A))))
    multiple = (
        DATA / "participant-a/catalog-v1.ttl"
    ).read_text() + "\n<urn:second> a dcat:Catalog ; dcat:contactPoint <urn:contact> ."
    response = client.post(
        "/catalog",
        content=multiple,
        headers={"Authorization": f"Bearer {TOKEN_A}", "Content-Type": "text/turtle"},
    )
    assert response.status_code == 422
    assert "exactly one" in str(response.json())
    assert set(index.graph(URIRef(graph_uri_for_participant(A)))) == before


def test_shared_resource_ids_keep_publisher_details_separate(system):
    client, _, _ = system
    from tests.fixtures import VALID_TURTLE

    for token, title in [(TOKEN_A, "Publisher A only"), (TOKEN_B, "Publisher B only")]:
        response = client.post(
            "/catalog",
            content=VALID_TURTLE.replace("Test dataset", title),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "text/turtle"},
        )
        assert response.status_code == 200
    rows = client.get("/datasets").json()
    assert len(rows) == 2
    assert len(client.get("/catalogs").json()) == 2
    params = {"dataset_id": rows[0]["dataset_id"]}
    assert client.get("/datasets/detail", params=params).status_code == 409
    for row in rows:
        detail = client.get(
            "/datasets/detail", params={**params, "graph": row["metadata"]["graph"]}
        ).json()
        assert detail["title"] == row["title"]
        assert detail["provider"] == row["provider"]
        other = "Publisher B only" if row["provider"] == A else "Publisher A only"
        assert other not in str(detail)
    assert (
        client.get("/datasets/detail", params={**params, "graph": "urn:missing"}).status_code == 404
    )


def test_empty_catalog_replaces_previous_and_changed_catalog_id_does_not_append(system):
    client, index, _ = system
    assert publish(client, TOKEN_A, "participant-a/catalog-v1.ttl").status_code == 200
    assert publish(client, TOKEN_B, "participant-b/catalog-v1.ttl").status_code == 200
    before = set(index.graph(URIRef(graph_uri_for_participant(B))))
    empty = "@prefix dcat: <http://www.w3.org/ns/dcat#> . <urn:new-catalog> a dcat:Catalog ; dcat:contactPoint <urn:contact> ."
    assert (
        client.post(
            "/catalog",
            content=empty,
            headers={"Authorization": f"Bearer {TOKEN_A}", "Content-Type": "text/turtle"},
        ).status_code
        == 200
    )
    catalogs = client.get("/catalogs").json()
    own = [row for row in catalogs if row["provider"] == A]
    assert len(own) == 1 and own[0]["catalog_id"] == "urn:new-catalog"
    assert own[0]["dataset_count"] == 0
    assert all(row["provider"] == B for row in client.get("/datasets").json())
    assert set(index.graph(URIRef(graph_uri_for_participant(B)))) == before


def test_unlinked_dataset_rejected_and_keywords_searchable(system):
    client, _, _ = system
    from tests.fixtures import VALID_TURTLE

    payload = (
        VALID_TURTLE
        + '\n<https://example.org/datasets/test> <http://www.w3.org/ns/dcat#keyword> "Structural inspection" .'
    )
    headers = {"Authorization": f"Bearer {TOKEN_A}", "Content-Type": "text/turtle"}
    assert client.post("/catalog", content=payload, headers=headers).status_code == 200
    assert len(client.get("/datasets", params={"q": "structural"}).json()) == 1
    orphan = "\n<urn:orphan> a <http://www.w3.org/ns/dcat#Dataset> ."
    assert client.post("/catalog", content=payload + orphan, headers=headers).status_code == 422
    assert len(client.get("/datasets", params={"q": "structural"}).json()) == 1


def test_aas_submodels_across_three_sources_replace_and_asset_identity(system):
    client, index, _ = system
    for token, path in [
        (TOKEN_A, "manufacturer-v1.ttl"),
        (TOKEN_B, "environment-v1.ttl"),
        (TOKEN_C, "operator-v1.ttl"),
    ]:
        response = publish(client, token, "aas-dpp/" + path)
        assert response.status_code == 200, response.json()
    query = (DATA / "aas-dpp/asset-submodels.rq").read_text()

    def results():
        response = client.post("/sparql", json={"query": query})
        assert response.status_code == 200, response.json()
        return response.json()["results"]["bindings"]

    rows = results()
    assert len(rows) == 3
    assert len({row["graph"]["value"] for row in rows}) == 3
    assert len({row["submodel"]["value"] for row in rows}) == 3
    assert {row["shell"]["value"] for row in rows} == {
        "https://example.org/aas-dpp/shells/pump-001"
    }
    assert len(client.get("/datasets", params={"q": "Pump 001"}).json()) == 3
    before = {owner: set(index.graph(URIRef(graph_uri_for_participant(owner)))) for owner in (A, B)}
    assert publish(client, TOKEN_C, "aas-dpp/operator-v2.ttl").status_code == 200
    rows = results()
    assert len(rows) == 3
    assert any(row["title"]["value"] == "Maintenance history — revision 2" for row in rows)
    for owner in (A, B):
        assert set(index.graph(URIRef(graph_uri_for_participant(owner)))) == before[owner]

    # Same keywords and type, but another asset ID: semantic discovery must exclude it.
    other_asset = (
        (DATA / "aas-dpp/environment-v1.ttl")
        .read_text()
        .replace("assets/pump-001", "assets/pump-002")
    )
    response = client.post(
        "/catalog",
        content=other_asset,
        headers={"Authorization": f"Bearer {TOKEN_B}", "Content-Type": "text/turtle"},
    )
    assert response.status_code == 200
    assert len(results()) == 2
    assert len(client.get("/datasets", params={"q": "Pump 001"}).json()) == 3


def test_group_api_snapshot_is_findable_and_links_back_to_source(system):
    client, _, _ = system
    response = publish(client, TOKEN_A, "group-aas/catalog.ttl")
    assert response.status_code == 200, response.json()
    report = json.loads((DATA / "group-aas/catalog.report.json").read_text())
    assert len(client.get("/datasets").json()) == report["submodels"]
    dpp = client.get("/datasets", params={"q": "DPP-EU"}).json()
    assert len(dpp) == 1 and "Template" in dpp[0]["title"]
    detail = client.get(
        "/datasets/detail",
        params={"dataset_id": dpp[0]["dataset_id"], "graph": dpp[0]["metadata"]["graph"]},
    ).json()
    access = [
        row["object"]
        for row in detail["triples"]
        if row["predicate"] == "http://www.w3.org/ns/dcat#accessURL"
    ]
    assert len(set(access)) == 1
    assert access[0].startswith(report["source_api"] + "/submodels/")
    rows = client.post(
        "/sparql", json={"query": (DATA / "group-aas/submodels.rq").read_text()}
    ).json()["results"]["bindings"]
    assert len(rows) == report["submodels"]
    assert sum("asset" in row for row in rows) == report["shell_linked_submodels"]
    dpp_rows = [row for row in rows if "DPP-EU" in row["title"]["value"]]
    assert len(dpp_rows) == 1 and "asset" not in dpp_rows[0] and "shell" not in dpp_rows[0]
    assert (
        dpp_rows[0]["semanticType"]["value"]
        == "https://admin-shell.io/submodels/DigitalProductPassport/1/0"
    )
