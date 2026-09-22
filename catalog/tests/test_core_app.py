import importlib
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

PARTICIPANTS = '{"urn:demo:a":"aaaaaaaa","urn:demo:b":"bbbbbbbb"}'


class _SequenceDiscovery:
    def __init__(self, statuses: list[dict[str, object]]) -> None:
        self._statuses = iter(statuses)
        self.calls = 0

    def get_status(self) -> dict[str, object]:
        self.calls += 1
        return next(self._statuses)


def _status(fuseki_ready: bool, detail: str | None = None) -> dict[str, object]:
    return {
        "mode": "http-demo",
        "operational": fuseki_ready,
        "detail": detail,
        "dependencies": {"fuseki": fuseki_ready, "participant_config": True},
    }


def _load_app_module(monkeypatch):
    monkeypatch.setenv("CATALOG_MODE", "http-demo")
    monkeypatch.setenv("EDC_DEMO_PARTICIPANTS", PARTICIPANTS)
    monkeypatch.setenv("CATALOG_STARTUP_CHECKS", "false")
    import core.app as app_module

    return importlib.reload(app_module)


def test_core_app_imports_http_demo(monkeypatch) -> None:
    app_module = _load_app_module(monkeypatch)

    assert app_module.app.title == "Federated Catalog HTTP Ingestion Demo"


def test_catalog_has_no_cors_headers_when_cors_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("CATALOG_CORS_ORIGINS", raising=False)
    app_module = _load_app_module(monkeypatch)
    client = TestClient(app_module.app)

    response = client.get("/health", headers={"Origin": "https://unrelated.example"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_startup_checks_retry_fuseki_until_reachable(monkeypatch) -> None:
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setenv("CATALOG_STARTUP_CHECKS", "true")
    monkeypatch.setenv("CATALOG_STARTUP_WAIT_SECONDS", "5")
    monkeypatch.setenv("CATALOG_STARTUP_RETRY_SECONDS", "0.25")

    discovery = _SequenceDiscovery(
        [
            _status(False, "Catalog discovery unavailable: connection refused"),
            _status(True),
        ]
    )
    mode = SimpleNamespace(name="http-demo", discovery=discovery)
    sleeps: list[float] = []
    monotonic_values = iter([10.0, 10.0])
    monkeypatch.setattr(app_module.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(app_module.time, "sleep", sleeps.append)

    app_module._startup_checks(mode)

    assert discovery.calls == 2
    assert sleeps == [0.25]


def test_startup_checks_raise_after_fuseki_wait_expires(monkeypatch) -> None:
    app_module = _load_app_module(monkeypatch)
    monkeypatch.setenv("CATALOG_STARTUP_CHECKS", "true")
    monkeypatch.setenv("CATALOG_STARTUP_WAIT_SECONDS", "0")

    discovery = _SequenceDiscovery([_status(False, "connection refused")])
    mode = SimpleNamespace(name="http-demo", discovery=discovery)
    monkeypatch.setattr(app_module.time, "monotonic", lambda: 10.0)

    with pytest.raises(RuntimeError, match="Fuseki is not reachable"):
        app_module._startup_checks(mode)

    assert discovery.calls == 1
