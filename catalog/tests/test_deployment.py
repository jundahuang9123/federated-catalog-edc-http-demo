import json

import pytest

from core.deployment import validate_deployment


def _production_settings():
    return {
        "CATALOG_DEPLOYMENT": "production",
        "CATALOG_MODE": "http-demo",
        "CATALOG_PUBLIC_URL": "https://catalog.example",
        "FUSEKI_PASSWORD": "f" * 64,
        "EDC_DEMO_PARTICIPANTS": json.dumps(
            {
                "urn:demo:participant:a": "a" * 64,
                "urn:demo:participant:b": "b" * 64,
            }
        ),
    }


def _apply(monkeypatch, settings):
    for key, value in settings.items():
        monkeypatch.setenv(key, value)


def test_complete_production_configuration(monkeypatch):
    _apply(monkeypatch, _production_settings())

    validate_deployment()


def test_production_rejects_wrong_mode(monkeypatch):
    settings = _production_settings()
    settings["CATALOG_MODE"] = "solid"
    _apply(monkeypatch, settings)

    with pytest.raises(RuntimeError, match="http-demo"):
        validate_deployment()


def test_production_rejects_weak_or_duplicate_participant_tokens(monkeypatch):
    settings = _production_settings()
    settings["EDC_DEMO_PARTICIPANTS"] = json.dumps({"urn:demo:a": "same", "urn:demo:b": "same"})
    _apply(monkeypatch, settings)

    with pytest.raises(RuntimeError):
        validate_deployment()


def test_production_requires_https_origin_without_path(monkeypatch):
    settings = _production_settings()
    settings["CATALOG_PUBLIC_URL"] = "https://catalog.example/subpath"
    _apply(monkeypatch, settings)

    with pytest.raises(RuntimeError, match="origin"):
        validate_deployment()


def test_production_rejects_credentials_in_public_url(monkeypatch):
    settings = _production_settings()
    settings["CATALOG_PUBLIC_URL"] = "https://user:secret@catalog.example"
    _apply(monkeypatch, settings)

    with pytest.raises(RuntimeError, match="HTTPS URL"):
        validate_deployment()


@pytest.mark.parametrize(
    "origin",
    ["*", "http://publisher.example", "https://publisher.example/path"],
)
def test_production_rejects_unsafe_cors_origins(monkeypatch, origin):
    settings = _production_settings()
    settings["CATALOG_CORS_ORIGINS"] = origin
    _apply(monkeypatch, settings)

    with pytest.raises(RuntimeError, match="HTTPS origins"):
        validate_deployment()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CATALOG_MAX_INGEST_BYTES", "0"),
        ("SPARQL_MAX_ROWS", "not-a-number"),
        ("FUSEKI_TIMEOUT_SECONDS", "-1"),
    ],
)
def test_production_rejects_invalid_numeric_limits(monkeypatch, name, value):
    settings = _production_settings()
    settings[name] = value
    _apply(monkeypatch, settings)

    with pytest.raises(RuntimeError, match=name):
        validate_deployment()
