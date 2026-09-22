"""Export discovery metadata from a BaSyx AAS API; never modify or publish source data."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from rdflib import DCAT, DCTERMS, RDF, RDFS, XSD, Graph, Literal, Namespace, URIRef

CX = Namespace("https://w3id.org/construct-dcat#")
MAX_BYTES = 8_000_000


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def valid_iri(value):
    return (
        isinstance(value, str)
        and bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value))
        and not any(
            char.isspace() or ord(char) < 32 or char in '<>"{}|^`\\' for char in value
        )
    )


def identity(value, kind):
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing {kind} identifier")
    return URIRef(
        value if valid_iri(value) else f"urn:aas:{kind}:{quote(value, safe='')}"
    )


def api_base(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Use an HTTP(S) API base without credentials, query or fragment"
        )
    _ = parsed.port
    return value.rstrip("/")


def endpoint(base, collection, identifier):
    encoded = (
        base64.urlsafe_b64encode(identifier.encode("utf-8")).decode("ascii").rstrip("=")
    )
    return f"{base}/{collection}/{encoded}"


def fetch_json(url):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "construct-dcat-discovery-export/1.0",
        },
    )
    with build_opener(NoRedirect()).open(request, timeout=25) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("API response exceeds metadata export limit")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise TypeError("Expected an API JSON object")
    return result


def paginated(base, collection, fetch=fetch_json, **extra):
    records, seen_ids, seen_cursors = [], set(), set()
    cursor = None
    for _ in range(100):
        params = {"limit": 50, **extra}
        if cursor:
            params["cursor"] = cursor
        page = fetch(base + "/" + collection + "?" + urlencode(params))
        rows = page.get("result")
        if not isinstance(rows, list):
            raise TypeError(f"Invalid {collection} listing")
        for row in rows:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("id"), str)
                or not row["id"]
            ):
                raise ValueError(f"Missing identifier in {collection} listing")
            if row["id"] in seen_ids:
                raise ValueError(f"Repeated identifier in {collection}; export aborted")
            seen_ids.add(row["id"])
            records.append(row)
        cursor = (page.get("paging_metadata") or {}).get("cursor")
        if not cursor:
            return records
        if not isinstance(cursor, str) or cursor in seen_cursors:
            raise ValueError(f"Repeated or invalid {collection} cursor")
        seen_cursors.add(cursor)
    raise ValueError("Pagination limit reached; refusing an incomplete snapshot")


def submodel_refs(shell):
    values = []
    for ref in shell.get("submodels") or []:
        keys = ref.get("keys") or []
        if (
            ref.get("type") != "ModelReference"
            or len(keys) != 1
            or keys[0].get("type") != "Submodel"
        ):
            raise ValueError(
                "Unsupported shell submodel reference; inspect before mapping"
            )
        values.append(keys[0]["value"])
    return values


def add_languages(graph, subject, predicate, values):
    for value in values or []:
        if isinstance(value, dict) and isinstance(value.get("text"), str):
            graph.add(
                (
                    subject,
                    predicate,
                    Literal(value["text"], lang=value.get("language") or None),
                )
            )


def build_catalog(base, shells, submodels, catalog_id, contact, captured_at):
    if not valid_iri(catalog_id) or not valid_iri(contact):
        raise ValueError("Catalog and contact must be absolute IRIs")
    by_id = {item["id"]: item for item in submodels}
    if len(by_id) != len(submodels):
        raise ValueError("Duplicate submodel identifiers")
    owners = {sm_id: [] for sm_id in by_id}
    for shell in shells:
        for sm_id in submodel_refs(shell):
            if sm_id not in by_id:
                raise ValueError(
                    "Shell references a missing submodel; refusing incomplete export"
                )
            owners[sm_id].append(shell)
    graph = Graph()
    for prefix, namespace in [
        ("cx", CX),
        ("dcat", DCAT),
        ("dct", DCTERMS),
        ("rdfs", RDFS),
    ]:
        graph.bind(prefix, namespace)
    catalog = URIRef(catalog_id)
    graph.add((catalog, RDF.type, DCAT.Catalog))
    graph.add(
        (
            catalog,
            DCTERMS.title,
            Literal("Group AAS API — submodel discovery", lang="en"),
        )
    )
    graph.add((catalog, DCTERMS.source, URIRef(base + "/swagger-ui/index.html")))
    graph.add((catalog, DCAT.contactPoint, URIRef(contact)))
    graph.add((catalog, DCTERMS.modified, Literal(captured_at, datatype=XSD.dateTime)))
    graph.add(
        (
            catalog,
            DCTERMS.description,
            Literal(
                "Discovery metadata extracted from the source API. Underlying AAS values remain at the source. Template labels and semantic identifiers are source assertions, not verified conformity claims.",
                lang="en",
            ),
        )
    )
    linked = 0
    for sm_id, sm in sorted(by_id.items()):
        sm_node = identity(sm_id, "submodel")
        record = URIRef(
            "urn:catalog-record:aas-submodel:"
            + hashlib.sha256(sm_id.encode()).hexdigest()
        )
        distribution = URIRef(str(record) + ":distribution")
        name = sm.get("idShort") or sm_id
        kind = sm.get("kind") or "unspecified kind"
        asset_ids = sorted(
            {
                shell.get("assetInformation", {}).get("globalAssetId")
                for shell in owners[sm_id]
            }
            - {None, ""}
        )
        suffix = ", ".join(item.rsplit("/", 1)[-1] for item in asset_ids)
        title = f"{name} — {kind}" + (f" — {suffix}" if suffix else "")
        for class_id in (DCAT.Dataset, CX.AASDataset):
            graph.add((record, RDF.type, class_id))
        graph.add((catalog, DCAT.dataset, record))
        graph.add((record, DCTERMS.title, Literal(title)))
        graph.add((record, DCTERMS.identifier, Literal(sm_id)))
        graph.add((record, CX.hasAASSubmodel, sm_node))
        graph.add((record, DCAT.distribution, distribution))
        graph.add((distribution, RDF.type, DCAT.Distribution))
        access = URIRef(endpoint(base, "submodels", sm_id))
        graph.add((distribution, DCAT.accessURL, access))
        graph.add((distribution, DCAT.mediaType, Literal("application/json")))
        graph.add((sm_node, RDFS.seeAlso, access))
        graph.add((sm_node, DCTERMS.identifier, Literal(sm_id)))
        graph.add((sm_node, RDFS.label, Literal(name)))
        add_languages(graph, record, DCTERMS.description, sm.get("description"))
        add_languages(graph, record, DCTERMS.alternative, sm.get("displayName"))
        for keyword in ("AAS", str(name), str(kind), *asset_ids):
            graph.add((record, DCAT.keyword, Literal(keyword)))
        ref = sm.get("semanticId") or {}
        keys = ref.get("keys") or []
        if (
            ref.get("type") == "ExternalReference"
            and len(keys) == 1
            and keys[0].get("type") == "GlobalReference"
        ):
            value = keys[0].get("value")
            if value:
                # Demo convention: semanticId as a type reference, not a conformity assertion.
                graph.add((record, DCTERMS.type, identity(value, "semantic-id")))
                graph.add((sm_node, DCTERMS.type, identity(value, "semantic-id")))
                graph.add((record, DCAT.keyword, Literal(value)))
        elif ref:
            raise ValueError("Unsupported semantic reference; inspect before mapping")
        if owners[sm_id]:
            linked += 1
        else:
            graph.add(
                (
                    record,
                    DCTERMS.description,
                    Literal(
                        "No shell reference was found in the inspected API. No asset or shell association is inferred.",
                        lang="en",
                    ),
                )
            )
        for shell in owners[sm_id]:
            shell_node = identity(shell["id"], "shell")
            graph.add((sm_node, DCTERMS.isPartOf, shell_node))
            graph.add((shell_node, DCTERMS.identifier, Literal(shell["id"])))
            graph.add(
                (
                    shell_node,
                    RDFS.seeAlso,
                    URIRef(endpoint(base, "shells", shell["id"])),
                )
            )
            asset_id = shell.get("assetInformation", {}).get("globalAssetId")
            if asset_id:
                asset = identity(asset_id, "asset")
                for node in (record, sm_node, shell_node):
                    graph.add((node, DCTERMS.subject, asset))
                graph.add((asset, DCTERMS.identifier, Literal(asset_id)))
    summary = {
        "source_api": base,
        "captured_at": captured_at,
        "shells": len(shells),
        "submodels": len(submodels),
        "shell_linked_submodels": linked,
        "unlinked_submodels": len(submodels) - linked,
        "templates": sum(sm.get("kind") == "Template" for sm in submodels),
        "instances": sum(sm.get("kind") == "Instance" for sm in submodels),
        "catalog_contact": contact,
    }
    return graph, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", required=True)
    parser.add_argument("--catalog-id", required=True)
    parser.add_argument(
        "--contact", required=True, help="Operator-provided catalog contact IRI"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--verify-links",
        action="store_true",
        help="GET each submodel and shell endpoint and check its returned ID",
    )
    args = parser.parse_args()
    base = api_base(args.api_base)
    shells = paginated(base, "shells")
    submodels = paginated(base, "submodels", level="core")
    verified = 0
    if args.verify_links:
        for collection, items in (("submodels", submodels), ("shells", shells)):
            for item in items:
                response = fetch_json(endpoint(base, collection, item["id"]))
                if response.get("id") != item["id"]:
                    raise ValueError(
                        "Access endpoint returned an unexpected identifier"
                    )
                verified += 1
                # Source values are deliberately neither copied to output nor logged.
    captured = datetime.now(UTC).isoformat()
    graph, summary = build_catalog(
        base, shells, submodels, args.catalog_id, args.contact, captured
    )
    from core.shared.shacl_validate import validate_rdf

    ttl = graph.serialize(format="turtle")
    result = validate_rdf(ttl, format="turtle")
    if not result.ok:
        raise ValueError(
            "Generated catalog failed validation: " + "; ".join(result.errors)
        )
    summary["verified_access_links"] = verified
    summary["verification"] = (
        "HTTP GET with matching id" if args.verify_links else "not checked"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(args.output.suffix + ".tmp")
    temp.write_text(ttl, encoding="utf-8")
    temp.replace(args.output)
    args.output.with_suffix(".report.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print(f"Wrote {args.output}; no metadata has been published to a catalog.")


if __name__ == "__main__":
    main()
