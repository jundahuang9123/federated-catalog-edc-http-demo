#!/usr/bin/env python3
"""Exercise the complete catalog-only HTTP demo in an isolated Compose project."""

import json
import subprocess
import time
from http.client import RemoteDisconnected
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "catalog-http-test-" + uuid4().hex[:10]
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", "docker-compose.integration.yml"]

PARTICIPANT_A = "urn:connector:participant-a"
PARTICIPANT_B = "urn:connector:participant-b"
TOKEN_A = "a1" * 32
TOKEN_B = "b2" * 32
INVALID_TOKEN = "c3" * 32

base = ""


def compose(*args: str) -> str:
    return subprocess.run(
        COMPOSE + list(args),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def request(
    path: str,
    body: bytes | dict | None = None,
    *,
    token: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, object]:
    request_headers = dict(headers or {})
    if isinstance(body, dict):
        body = json.dumps(body).encode()
        request_headers["Content-Type"] = "application/json"
    elif body is not None:
        request_headers["Content-Type"] = "text/turtle"
    if token:
        request_headers["Authorization"] = f"Bearer {token}"

    try:
        with urlopen(
            Request(base + path, data=body, headers=request_headers),
            timeout=30,
        ) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def wait_ready() -> None:
    global base
    base = "http://" + compose("port", "catalog", "8000").strip()
    for _attempt in range(90):
        try:
            if request("/ready")[0] == 200:
                return
        except (URLError, TimeoutError, ConnectionError, RemoteDisconnected):
            pass
        time.sleep(2)
    raise RuntimeError("Catalog did not become ready")


def publish(token: str, fixture: str, *, headers: dict[str, str] | None = None):
    return request(
        "/catalog",
        (ROOT / "demo-data" / fixture).read_bytes(),
        token=token,
        headers=headers,
    )


def query(text: str) -> dict:
    code, result = request("/sparql", {"query": text})
    assert code == 200, result
    assert isinstance(result, dict)
    return result


def graph_snapshot(participant: str) -> set[str]:
    graph = "urn:catalog:" + quote(participant, safe="")
    rows = query(f"SELECT ?s ?p ?o WHERE {{ GRAPH <{graph}> {{ ?s ?p ?o }} }}")[
        "results"
    ]["bindings"]
    return {json.dumps(row, sort_keys=True) for row in rows}


def dataset_providers() -> dict[str, str | None]:
    status, payload = request("/datasets")
    assert status == 200, payload
    assert isinstance(payload, list)
    return {item["dataset_id"]: item.get("provider") for item in payload}


def assert_rejected_without_mutation(
    token: str, fixture: str, expected_status: int
) -> None:
    before_a = graph_snapshot(PARTICIPANT_A)
    before_b = graph_snapshot(PARTICIPANT_B)
    status, _payload = publish(token, fixture)
    assert status == expected_status
    assert graph_snapshot(PARTICIPANT_A) == before_a
    assert graph_snapshot(PARTICIPANT_B) == before_b


if __name__ == "__main__":
    try:
        print(f"Starting disposable integration project {PROJECT}", flush=True)
        compose("up", "-d", "--build")
        wait_ready()

        status, payload = publish(TOKEN_A, "participant-a/catalog-v1.ttl")
        assert status == 200, payload
        assert payload["participant_id"] == PARTICIPANT_A
        assert payload["interface"] == "edc-http-adapter-simulator"

        status, payload = publish(TOKEN_B, "participant-b/catalog-v1.ttl")
        assert status == 200, payload
        assert payload["participant_id"] == PARTICIPANT_B

        assert_rejected_without_mutation(
            INVALID_TOKEN,
            "participant-a/catalog-v2.ttl",
            401,
        )
        assert (
            request(
                "/catalog",
                (ROOT / "demo-data/participant-a/catalog-v1.ttl").read_bytes(),
            )[0]
            == 401
        )
        assert (
            publish(
                TOKEN_A,
                "participant-a/catalog-v1.ttl",
                headers={"X-Participant-Id": PARTICIPANT_B},
            )[0]
            == 403
        )

        status, catalogs = request("/catalogs")
        assert status == 200 and len(catalogs) == 2
        assert {row["provider"] for row in catalogs} == {PARTICIPANT_A, PARTICIPANT_B}
        assert sum(row["dataset_count"] for row in catalogs) == 3
        status, matches = request("/datasets?q=FRAME")
        assert status == 200 and len(matches) == 1
        assert matches[0]["metadata"]["catalog_id"].endswith("a-catalog")

        providers = dataset_providers()
        assert len(providers) == 3
        assert providers["https://example.org/live-demo/a-frame"] == PARTICIPANT_A
        assert providers["https://example.org/live-demo/b-components"] == PARTICIPANT_B
        status, detail = request(
            "/datasets/detail?dataset_id=https%3A%2F%2Fexample.org%2Flive-demo%2Fa-frame"
        )
        assert status == 200 and detail["provider"] == PARTICIPANT_A

        walls = (ROOT / "demo-data/queries/walls.rq").read_text()
        assert len(query(walls)["results"]["bindings"]) == 2
        assert query("ASK {}")["boolean"] is True

        b_before = graph_snapshot(PARTICIPANT_B)
        status, payload = publish(TOKEN_A, "participant-a/catalog-v2.ttl")
        assert status == 200, payload
        a_after = graph_snapshot(PARTICIPANT_A)
        assert graph_snapshot(PARTICIPANT_B) == b_before
        assert not any("a-slabs" in row for row in a_after)
        assert any("a-panels" in row for row in a_after)
        assert len(query(walls)["results"]["bindings"]) == 3

        status, payload = publish(TOKEN_A, "invalid/invalid-catalog.ttl")
        assert status == 422 and payload["stage"] == "validation"
        assert graph_snapshot(PARTICIPANT_A) == a_after
        assert graph_snapshot(PARTICIPANT_B) == b_before

        for unsafe in [
            "DROP ALL",
            "SELECT ???",
            "SELECT * WHERE { SERVICE <http://example.org> { ?s ?p ?o } }",
        ]:
            assert request("/sparql", {"query": unsafe})[0] == 400

        compose("stop", "fuseki")
        status, payload = publish(TOKEN_A, "participant-a/catalog-v1.ttl")
        assert status == 502 and payload["stage"] == "store"
        assert request("/ready")[0] == 503
        compose("start", "fuseki")
        wait_ready()
        assert graph_snapshot(PARTICIPANT_A) == a_after
        assert graph_snapshot(PARTICIPANT_B) == b_before

        print("Recreating all containers while retaining the named volume", flush=True)
        compose("down")
        compose("up", "-d")
        wait_ready()
        assert len(dataset_providers()) == 3
        assert graph_snapshot(PARTICIPANT_A) == a_after
        assert graph_snapshot(PARTICIPANT_B) == b_before
        assert len(query(walls)["results"]["bindings"]) == 3
        # Exercise the partner presentation against real Fuseki, after persistence checks.
        assert publish(TOKEN_A, "participant-a/catalog-v1.ttl")[0] == 200
        status, payload = publish(TOKEN_B, "participant-b/catalog-connector-demo.ttl")
        assert status == 200, payload
        status, catalogs = request("/catalogs")
        assert status == 200 and sum(c["dataset_count"] for c in catalogs) == 4
        b_catalog = next(c for c in catalogs if c["provider"] == PARTICIPANT_B)
        assert len(b_catalog["metadata"]["hierarchy"]) == 4
        status, matches = request("/datasets?q=did%3Aweb%3Aparticipant-b")
        assert status == 200 and len(matches) == 2
        row = next(d for d in matches if d["metadata"]["asset_id"] == "b-components")
        status, detail = request(
            "/datasets/detail?dataset_id="
            + quote(row["dataset_id"], safe="")
            + "&graph="
            + quote(row["metadata"]["graph"], safe="")
        )
        assert status == 200
        assert detail["metadata"]["provider_did"] == "did:web:participant-b.example.org"
        assert (
            detail["metadata"]["dsp_endpoint"]
            == "https://participant-b.example.org/dsp/2025-1"
        )
        assert any(
            t["object_type"] == "literal" and t["language"] == "en"
            for t in detail["triples"]
        )
        links = (ROOT / "demo-data/queries/publisher-links.rq").read_text()
        assert len(query(links)["results"]["bindings"]) == 2
        print(
            "PASS: connector metadata, nested series, typed RDF, bearer identity, SHACL, discovery, SPARQL, graph isolation, "
            "replacement, dependency failure and persistence",
            flush=True,
        )
    except Exception:
        try:
            print(compose("logs", "--tail=100"))
        except subprocess.CalledProcessError as log_error:
            print(f"Could not collect Compose logs: {log_error}")
        raise
    finally:
        print(f"Removing isolated test project {PROJECT}", flush=True)
        compose("down", "--volumes", "--remove-orphans")
