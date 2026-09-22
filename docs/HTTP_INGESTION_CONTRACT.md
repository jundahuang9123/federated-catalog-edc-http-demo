# HTTP ingestion contract

## Purpose and scope

This is the custom interface demonstrated by this repository:

```http
POST /catalog
```

It accepts one participant's DCAT/RDF snapshot and replaces that participant's materialized catalog graph.

The included client simulates the HTTP delivery step an EDC-side adapter could call. This contract is not an Eclipse EDC or Dataspace Protocol endpoint. It does not provide DSP catalog exchange, contract negotiation, agreement verification, policy enforcement, transfer-process orchestration, an EDC control plane, or an EDC data plane.

## Participant configuration

The catalog operator configures the accepted participant credentials:

```dotenv
EDC_DEMO_PARTICIPANTS={"urn:demo:participant:a":"<token-a>","urn:demo:participant:b":"<token-b>"}
```

Production validation requires at least two entries. Each token must be unique and contain at least 64 hexadecimal characters. The mapping is a demo allowlist and credential store; it is not an EDC participant registry.

The token determines identity. If token A authenticates, the request owns participant A's graph regardless of the metadata's `dct:publisher` statements. The public Caddy proxy removes participant identity headers.

## Request

```http
POST /catalog HTTP/1.1
Host: catalog.example.org
Authorization: Bearer <participant-demo-token>
Content-Type: text/turtle
X-Request-Id: adapter-01H...

@prefix dcat: <http://www.w3.org/ns/dcat#> .
...
```

### Headers

| Header | Requirement |
| --- | --- |
| `Authorization` | Required. Scheme is `Bearer`; the value must match exactly one configured token. |
| `Content-Type` | Required. Send one of the RDF media types listed below. |
| `X-Request-Id` | Optional. Used for response correlation and logs; trimmed and limited to 128 characters. The service generates a UUID when absent. |
| `X-Participant-Id` | Do not use. The public proxy strips it and identity is derived from the token. |

Supported RDF media types:

- `text/turtle`
- `application/x-turtle`
- `application/ld+json`
- `application/json` (interpreted as JSON-LD)
- `application/rdf+xml`
- `application/n-triples`
- `application/n-quads`
- `application/trig`
- `text/n3`

JSON-LD contexts must be embedded in the document. Remote `@context` documents and `@import` are rejected so ingestion never fetches caller-selected URLs.

The body must be UTF-8, contain exactly one `dcat:Catalog` identified by an IRI that links to every included `dcat:Dataset` through `dcat:dataset` (optionally followed by `dcat:seriesMember`), and pass the catalog's SHACL validation. The application limit defaults to 2 MiB through `CATALOG_MAX_INGEST_BYTES`; Caddy also enforces a 2 MB outer limit in the supplied deployment.

A valid catalog with no datasets is accepted and removes that publisher’s previous dataset listings. Multiple catalogs and unlinked datasets are rejected with HTTP 422 before storage. Changing the catalog IRI still replaces the same token-owned snapshot.

### Curl example

```bash
curl --fail-with-body \
  -X POST https://catalog.example.org/catalog \
  -H "Authorization: Bearer ${EDC_SIMULATOR_TOKEN}" \
  -H 'Content-Type: text/turtle' \
  -H 'X-Request-Id: manual-demo-001' \
  --data-binary @demo-data/participant-a/catalog-v1.ttl
```

Prefer `scripts/edc_http_simulator.py` for demonstrations because it selects the configured token without putting it in command output and sets the media type from the RDF filename.

## Successful response

An accepted snapshot returns HTTP 200:

```json
{
  "accepted": true,
  "mode": "http-demo",
  "interface": "edc-http-adapter-simulator",
  "participant_id": "urn:demo:participant:a",
  "graph": "urn:catalog:urn%3Ademo%3Aparticipant%3Aa",
  "request_id": "adapter-01H..."
}
```

The graph name is generated as `urn:catalog:` plus the percent-encoded participant URI. A successful Graph Store `PUT` replaces the complete previous graph for that participant. It does not append a second version. Graphs belonging to other participants are unaffected.

Sending the same valid snapshot again is safe for the catalog state. When two different valid snapshots for one participant arrive concurrently, the last committed write is visible; the interface has no revision precondition or conflict response.

## Error response

Application rejections use a structured body:

```json
{
  "error": "validation_failed",
  "detail": "RDF payload failed parsing or SHACL validation",
  "stage": "validation",
  "request_id": "adapter-01H...",
  "errors": ["..."]
}
```

| Status | Stage | Meaning |
| --- | --- | --- |
| `401` | `auth` | Bearer credentials are absent, malformed or unknown. |
| `403` | `auth` | A direct, unproxied request declared a participant different from the token identity. Public Caddy removes that header. |
| `413` | `parse` | The application request-size limit was exceeded. Caddy can also return its own 413 before FastAPI. |
| `415` | `parse` | `Content-Type` is missing or the declared RDF media type is unsupported. |
| `422` | `validation` | The body is not UTF-8, cannot be parsed as the declared RDF format, or fails SHACL. |
| `502` | `store` | The validated graph could not be written to Fuseki. |

All failures before the store step leave the participant's last valid graph unchanged. A store error is reported as failed and should be investigated before retrying.

Authentication failures deliberately use the same message for unknown participants and wrong tokens so the endpoint does not reveal the configured mapping.

## Simulator use

With the mapping in `.env` or an ignored `.env.simulator`:

```bash
python3 scripts/edc_http_simulator.py \
  --catalog-url https://catalog.example.org/catalog \
  --participant urn:demo:participant:a \
  --env-file .env.simulator \
  --rdf demo-data/participant-a/catalog-v1.ttl
```

Recognized file suffixes are `.ttl`, `.json`, `.jsonld`, `.rdf`, `.xml`, `.nt`, `.nq`, `.trig` and `.n3`. The simulator refuses plain HTTP for remote hosts. It returns exit code 0 for a successful HTTP response, 1 for a rejected request or network failure, and 2 for local configuration errors.

## Adapter responsibilities for a future EDC integration

An actual EDC-side adapter can call this boundary after the EDC workflow has authorized the action and produced the catalog snapshot. That adapter would need to:

1. obtain the DCAT/RDF from the intended EDC event or extension point;
2. map the authenticated EDC participant context to a catalog credential held in a secret store;
3. serialize a complete participant snapshot with an accurate media type;
4. send the request over HTTPS with a stable correlation ID;
5. treat non-2xx responses as an unsuccessful catalog publication and apply bounded retry rules;
6. keep EDC negotiation, agreement and policy evidence in the EDC system rather than implying that the bearer token proves those events.

Those responsibilities are an integration design. They are not implemented by this repository.
