# Architecture

[Documentation index](README.md) · [Illustrated workflow](workflow.html)

## The model

The federated catalog is a catalog of publisher catalogs. Each authenticated publisher owns one complete snapshot in its own named graph. Its catalog and dataset identifiers remain visible in combined search and query results.

A publisher sends DCAT/RDF metadata using `POST /catalog`. The catalog checks the token, validates the content, and replaces that publisher's snapshot. The referenced data files remain with their providers. All catalog metadata is publicly readable.

## Responsibilities

| Component | What it does |
| --- | --- |
| Individual browser publisher | Runs locally, reads a selected DCAT file, sends it through a local Python sender with the participant token |
| CLI simulator | Sends the same HTTP request without the browser |
| Caddy | Provides the one public HTTPS origin and proxies to the catalog |
| Catalog service | Authenticates, validates, stores and exposes discovery and read-only queries |
| Fuseki | Persists one named graph per publisher in a central TDB2 dataset |

Only Caddy exposes public server ports. The local browser publisher needs no domain: its Python sender makes the remote request, so the catalog needs no browser CORS change. Neither client runs Eclipse EDC or DSP. [Publisher setup](../publisher/README.md) · [Server deployment](DEPLOYMENT.md).

## Ownership and replacement

`EDC_DEMO_PARTICIPANTS` maps each participant URI to its unique bearer token. The catalog derives the graph as `urn:catalog:` plus the percent-encoded participant URI. RDF publisher labels and client-selected catalog identifiers do not determine graph ownership. Caddy strips participant identity headers; the application also rejects a conflicting identity header when reached directly.

A valid snapshot contains exactly one IRI-identified `dcat:Catalog`, linking all included datasets directly or through dataset series. An empty catalog is allowed. Changing the catalog IRI still replaces the same publisher's snapshot.

Authentication, parsing and validation occur before storage. One Graph Store `PUT` replaces the graph with no preceding delete. Rejected input preserves the previous version. Omitted datasets disappear from that publisher's contribution; other graphs are unchanged. Concurrent accepted writes for one publisher use the last committed snapshot; there is no version-conflict protocol.

[Full ingestion contract](HTTP_INGESTION_CONTRACT.md)

## Discovery

`GET /catalogs` lists source catalogs. Dataset discovery returns one result per source graph and dataset identifier, with `metadata.catalog_id` and `metadata.graph`. Details use the selected graph; an unscoped identifier shared by multiple sources returns HTTP 409 instead of mixing their descriptions.

Keyword search is case-insensitive substring matching across the combined dataset listings, available in the browser and via `/datasets?q=...`. It is not a ranked full-text index.

`POST /sparql` accepts JSON containing SELECT or ASK, queries the central index, and returns SPARQL JSON results. It can inspect or join multiple named graphs. It does not contact remote SPARQL endpoints or allow updates. [SPARQL limits and examples](SPARQL.md).

Shared identifiers and explicit RDF links allow related records to be discovered together. A shared asset type alone does not identify the same individual asset. The [AAS/DPP scenario](AAS_DPP_SCENARIO.md) demonstrates the distinction.

## Scope and operations

This is a custom HTTP ingestion demo, not an EDC connector, an AAS server or a DPP assembler. Tokens are statically configured demo credentials. The operator generates and rotates them; changes require recreating the catalog container. Persistent metadata remains in the Fuseki volume across ordinary restarts.

See [requirements](REQUIREMENTS.md) for the intended behavior, [deployment](DEPLOYMENT.md) for operations, and [audit](AUDIT.md) for limitations and evidence boundaries.
