import pytest

from core.config import load_active_mode


def test_mode_switch_loads_http_demo_registration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATALOG_MODE", "http-demo")
    monkeypatch.setenv(
        "EDC_DEMO_PARTICIPANTS",
        '{"urn:demo:a":"token-a","urn:demo:b":"token-b"}',
    )

    assert load_active_mode().name == "http-demo"


@pytest.mark.parametrize("mode", ["solid", "edc", "invalid"])
def test_mode_switch_rejects_other_modes(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    monkeypatch.setenv("CATALOG_MODE", mode)

    with pytest.raises(RuntimeError):
        load_active_mode()
