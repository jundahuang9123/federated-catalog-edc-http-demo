from __future__ import annotations

import json

from rdflib import Graph

CONTENT_TYPE_TO_RDFLIB_FORMAT = {
    "application/ld+json": "json-ld",
    "application/json": "json-ld",
    "application/n-quads": "nquads",
    "application/n-triples": "nt",
    "application/rdf+xml": "xml",
    "application/trig": "trig",
    "application/x-turtle": "turtle",
    "text/n3": "n3",
    "text/turtle": "turtle",
}


def normalize_content_type(content_type: str | None) -> str:
    return (content_type or "text/turtle").split(";", 1)[0].strip().lower()


def guess_rdflib_format(content_type: str | None = None, explicit_format: str | None = None) -> str:
    if explicit_format:
        return explicit_format
    return CONTENT_TYPE_TO_RDFLIB_FORMAT.get(normalize_content_type(content_type), "turtle")


def _context_uses_remote_document(value: object) -> bool:
    if isinstance(value, str):
        return True
    if isinstance(value, list):
        return any(_context_uses_remote_document(item) for item in value)
    return isinstance(value, dict) and "@import" in value


def _reject_remote_jsonld_contexts(value: object) -> None:
    if isinstance(value, dict):
        if "@import" in value or (
            "@context" in value and _context_uses_remote_document(value["@context"])
        ):
            raise ValueError("Remote JSON-LD contexts and @import are not supported")
        for child in value.values():
            _reject_remote_jsonld_contexts(child)
    elif isinstance(value, list):
        for child in value:
            _reject_remote_jsonld_contexts(child)


def parse_rdf_payload(
    rdf_payload: str,
    *,
    content_type: str | None = None,
    format: str | None = None,
) -> Graph:
    selected_format = guess_rdflib_format(content_type, format)
    if selected_format == "json-ld":
        _reject_remote_jsonld_contexts(json.loads(rdf_payload))
    graph = Graph()
    graph.parse(data=rdf_payload, format=selected_format)
    return graph


def serialize_rdf_to_turtle(
    rdf_payload: str,
    *,
    content_type: str | None = None,
    format: str | None = None,
) -> str:
    graph = parse_rdf_payload(rdf_payload, content_type=content_type, format=format)
    serialized = graph.serialize(format="turtle")
    return serialized.decode("utf-8") if isinstance(serialized, bytes) else serialized
