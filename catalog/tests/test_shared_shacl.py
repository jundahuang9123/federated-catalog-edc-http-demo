import json

from core.shared.shacl_validate import ShaclValidationGate, validate_rdf
from tests.fixtures import INVALID_SHACL_TURTLE, VALID_TURTLE


def test_validate_rdf_accepts_conformant_dcat() -> None:
    result = validate_rdf(VALID_TURTLE, format="turtle")

    assert result.ok
    assert result.errors == []


def test_validate_rdf_rejects_nonconformant_dcat() -> None:
    result = validate_rdf(INVALID_SHACL_TURTLE, format="turtle")

    assert not result.ok
    assert result.errors


def test_validate_rdf_rejects_invalid_rdf() -> None:
    result = validate_rdf("this is not valid RDF", format="turtle")

    assert not result.ok
    assert "RDF parse error" in result.errors[0]


def test_validate_rdf_rejects_non_dcat_rdf() -> None:
    result = validate_rdf("<urn:s> <urn:p> <urn:o> .", format="turtle")

    assert not result.ok
    assert result.errors == ["RDF payload contains no dcat:Catalog"]


def test_validate_rdf_requires_catalog_dataset_link() -> None:
    result = validate_rdf(
        """
        @prefix dcat: <http://www.w3.org/ns/dcat#> .
        <urn:catalog> a dcat:Catalog ; dcat:contactPoint <urn:contact> .
        <urn:dataset> a dcat:Dataset ; dcat:distribution <urn:distribution> .
        <urn:distribution> a dcat:Distribution ; dcat:downloadURL <https://example.test/data> .
        """,
        format="turtle",
    )

    assert not result.ok
    assert "link to every dataset" in result.errors[0]


def test_validate_rdf_rejects_remote_jsonld_context_without_fetching() -> None:
    result = validate_rdf(
        json.dumps(
            {
                "@context": "http://127.0.0.1:9/context.jsonld",
                "@id": "urn:catalog",
                "@type": "http://www.w3.org/ns/dcat#Catalog",
            }
        ),
        format="json-ld",
    )

    assert not result.ok
    assert "Remote JSON-LD contexts" in result.errors[0]


def test_shacl_validation_gate_delegates_to_validator() -> None:
    gate = ShaclValidationGate()

    assert gate.validate(VALID_TURTLE, format="turtle").ok
