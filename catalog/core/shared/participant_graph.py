"""Stable named-graph identifiers for authenticated catalog participants."""

from urllib.parse import quote, unquote

GRAPH_PREFIX = "urn:catalog:"


def graph_uri_for_participant(participant_id: str) -> str:
    return f"{GRAPH_PREFIX}{quote(participant_id, safe='')}"


def participant_from_graph_uri(graph_uri: str | None) -> str | None:
    if not graph_uri or not graph_uri.startswith(GRAPH_PREFIX):
        return None
    return unquote(graph_uri[len(GRAPH_PREFIX) :])
