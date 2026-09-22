from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.shared.participant_graph import graph_uri_for_participant
from core.shared.shacl_validate import ShaclValidationGate
from modes.http_demo.auth import HttpDemoTokenAuth
from modes.http_demo.discovery import HttpDemoDiscovery
from modes.http_demo.ingest import HttpDemoIngest
from modes.http_demo.registry import DemoParticipantRegistry
from tests.fixtures import (
    INVALID_SHACL_TURTLE,
    VALID_TURTLE,
    VALID_TURTLE_REPLACEMENT,
    MemoryCatalogStore,
)

A = "urn:demo:participant:a"
B = "urn:demo:participant:b"
TOKEN_A = "a" * 64
TOKEN_B = "b" * 64


def _client(store=None):
    store = store or MemoryCatalogStore()
    registry = DemoParticipantRegistry({A: TOKEN_A, B: TOKEN_B})
    auth = HttpDemoTokenAuth(registry)
    app = FastAPI()
    app.include_router(
        HttpDemoIngest(
            validation=ShaclValidationGate(),
            store=store,
            auth=auth,
        ).routes()
    )
    discovery = HttpDemoDiscovery(store=store, registry=registry)
    return TestClient(app), store, discovery


def _publish(client, token, body=VALID_TURTLE, headers=None):
    request_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/turtle",
    }
    request_headers.update(headers or {})
    return client.post("/catalog", content=body, headers=request_headers)


def test_token_derived_participant_is_stored_and_discoverable():
    client, store, discovery = _client()

    response = _publish(client, TOKEN_A)

    assert response.status_code == 200
    assert response.json()["mode"] == "http-demo"
    assert response.json()["interface"] == "edc-http-adapter-simulator"
    assert response.json()["participant_id"] == A
    assert response.json()["graph"] == graph_uri_for_participant(A)
    assert len(store.graphs) == 1
    datasets = discovery.list_datasets()
    assert datasets[0].provider == A
    assert datasets[0].metadata["mode"] == "http-demo"


def test_missing_or_wrong_token_is_rejected_without_store_write():
    client, store, _ = _client()

    missing = client.post("/catalog", content=VALID_TURTLE, headers={"Content-Type": "text/turtle"})
    wrong = _publish(client, "wrong-token")

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.json()["stage"] == "auth"
    assert wrong.json()["error"] == "invalid_credentials"
    assert store.graphs == {}


def test_non_ascii_token_is_not_a_registry_match():
    registry = DemoParticipantRegistry({A: TOKEN_A, B: TOKEN_B})

    assert registry.participant_for_token("not-a-token-💥") is None


def test_declared_identity_cannot_override_token_identity():
    client, store, _ = _client()

    response = _publish(client, TOKEN_A, headers={"X-Participant-Id": B})

    assert response.status_code == 403
    assert response.json()["error"] == "participant_mismatch"
    assert store.graphs == {}


def test_rdf_publisher_cannot_override_token_identity():
    client, _, discovery = _client()
    payload = VALID_TURTLE.replace(
        'dct:title "Test dataset" ;',
        f'dct:title "Test dataset" ;\n    dct:publisher <{B}> ;',
    )

    response = _publish(client, TOKEN_A, payload)

    assert response.status_code == 200
    assert discovery.list_datasets()[0].provider == A


def test_invalid_rdf_and_shacl_rejection_preserve_existing_graph():
    client, store, _ = _client()
    assert _publish(client, TOKEN_A).status_code == 200
    before = dict(store.graphs)

    invalid_rdf = _publish(client, TOKEN_A, "this is not valid RDF")
    invalid_shape = _publish(client, TOKEN_A, INVALID_SHACL_TURTLE)

    assert invalid_rdf.status_code == 422
    assert invalid_shape.status_code == 422
    assert invalid_shape.json()["stage"] == "validation"
    assert store.graphs == before


def test_republish_replaces_only_authenticated_participant_graph():
    client, store, discovery = _client()
    assert _publish(client, TOKEN_A).status_code == 200
    assert _publish(client, TOKEN_B).status_code == 200
    b_before = store.graphs[graph_uri_for_participant(B)]

    assert _publish(client, TOKEN_A, VALID_TURTLE_REPLACEMENT).status_code == 200

    assert len(store.graphs) == 2
    assert store.graphs[graph_uri_for_participant(B)] == b_before
    assert any(item.title == "Replacement dataset" for item in discovery.list_datasets())


def test_unsupported_media_type_is_rejected():
    client, store, _ = _client()
    response = client.post(
        "/catalog",
        content=VALID_TURTLE,
        headers={"Authorization": f"Bearer {TOKEN_A}", "Content-Type": "text/plain"},
    )

    assert response.status_code == 415
    assert store.graphs == {}


def test_missing_content_type_is_rejected():
    client, store, _ = _client()
    response = client.post(
        "/catalog",
        content=VALID_TURTLE,
        headers={"Authorization": f"Bearer {TOKEN_A}"},
    )

    assert response.status_code == 415
    assert store.graphs == {}


def test_payload_limit_is_enforced_before_validation(monkeypatch):
    monkeypatch.setenv("CATALOG_MAX_INGEST_BYTES", "8")
    client, store, _ = _client()

    response = _publish(client, TOKEN_A)

    assert response.status_code == 413
    assert response.json()["stage"] == "parse"
    assert store.graphs == {}


def test_store_failure_is_controlled():
    class FailingStore(MemoryCatalogStore):
        def replace_graph(self, graph_id: str, rdf_payload: str) -> None:
            raise RuntimeError("index unavailable")

    client, _, _ = _client(FailingStore())
    response = _publish(client, TOKEN_A)

    assert response.status_code == 502
    assert response.json()["stage"] == "store"
