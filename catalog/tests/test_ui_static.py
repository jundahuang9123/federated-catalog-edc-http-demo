from pathlib import Path


def test_ui_uses_discovery_endpoints_without_solid_client_code() -> None:
    ui_text = "\n".join(path.read_text() for path in Path("ui").glob("*.*"))

    assert "/datasets" in ui_text
    assert "/catalogs" in ui_text
    assert "/sparql" in ui_text
    assert "/status" in ui_text
    assert "@inrupt" not in ui_text
    assert "solidCatalog" not in ui_text
    assert "Solid Pod" not in ui_text
    assert "WebID" not in ui_text
