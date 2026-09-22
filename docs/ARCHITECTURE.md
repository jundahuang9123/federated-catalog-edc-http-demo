# Architecture and trust boundary

## Demonstrated path

```text
Participant A fixture ----\
                           EDC HTTP adapter simulator
Participant B fixture ----/     |
                                | HTTPS POST /catalog
                                | Authorization: Bearer <demo token>
                                | Content-Type: text/turtle
                                v
                         Caddy reverse proxy
                                |
                         FastAPI catalog
                     1. authenticate token
                     2. derive participant URI
                     3. parse and SHACL-validate RDF
                     4. replace participant graph
                                |
                         Apache Jena Fuseki
                      persistent TDB2 dataset
                                |
             UI + GET discovery + bounded POST /sparql
```

The simulator represents only the final delivery action an adapter beside an EDC connector could perform after some external workflow has produced DCAT/RDF. This repository does not contain an Eclipse EDC runtime, DSP messaging, catalog exchange, contract negotiation, policy evaluation or enforcement, transfer orchestration, a control plane, or a data plane.

## Components

The simulator is a standard-library Python client. It chooses a token by participant URI from `.env`, infers the RDF media type from the file extension, creates a request ID and sends the RDF body. It does not send a participant identity header.

Caddy terminates HTTPS and proxies requests to FastAPI. It removes caller-supplied participant identity headers before forwarding, so public callers cannot use those headers to assign graph ownership. Only Caddy publishes host ports; FastAPI and Fuseki remain on Docker networks.

The FastAPI catalog maps a bearer token to one configured participant URI. It validates the RDF, normalizes it to Turtle, and replaces exactly that participant's graph through Fuseki's Graph Store Protocol. It also serves discovery, readiness, UI assets and the restricted query endpoint.

Fuseki stores one TDB2 dataset in the `fuseki-data` Docker volume. Its SPARQL query and Graph Store endpoints are available only to the catalog network. The assembler exposes no SPARQL Update endpoint.

## Identity and graph ownership

`EDC_DEMO_PARTICIPANTS` is the complete participant directory for this demonstration:

```json
{
  "urn:demo:participant:a": "<64-or-more-hex-characters>",
  "urn:demo:participant:b": "<different-64-or-more-hex-characters>"
}
```

The catalog compares the supplied token with the configured tokens and obtains the participant URI from the matching entry. A participant's graph is deterministic:

```text
urn:catalog:<percent-encoded-participant-URI>
```

For example, `urn:demo:participant:a` becomes `urn:catalog:urn%3Ademo%3Aparticipant%3Aa`. RDF statements such as `dct:publisher` do not decide ownership, and discovery reports the participant decoded from the graph name.

These shared bearer tokens are suitable only for the controlled demonstrator. They do not prove possession of an EDC identity, verify a DSP participant context, or express an EDC policy. A real integration should put an adapter behind the connector's authenticated workflow and give that adapter an appropriate service credential accepted by the catalog.

## Publication semantics

A successful request follows this sequence:

1. Authenticate the bearer token and derive the participant URI.
2. enforce the configured request-size bound;
3. parse the declared RDF format as UTF-8;
4. apply the catalog SHACL validation gate;
5. serialize the validated graph to Turtle;
6. use Graph Store `PUT` to replace the participant's named graph.

Authentication, media-type, parsing and SHACL failures occur before storage. One successful `PUT` replaces the graph; there is no preceding destructive delete. A failed validation therefore leaves the previous valid snapshot intact. Submissions from participant A never replace participant B's graph. Concurrent accepted writes for the same participant use last-committed-write semantics; this demo has no version or conflict protocol.

## Discovery and querying

`GET /datasets` and `GET /datasets/detail` query the materialized Fuseki dataset. `POST /sparql` accepts JSON containing a SELECT or ASK query. It rejects SPARQL Update, `SERVICE`, `FROM` dataset clauses and extension functions, and applies request, row, response-size, concurrency and time limits.

Queries can inspect several named graphs inside one Fuseki dataset. This is cross-participant querying over a materialized central index; it is not distributed SPARQL federation.

## Operational boundaries

The readiness endpoint checks Fuseki and the participant configuration. The participant mapping is loaded from deployment configuration, so changing participants or rotating tokens requires restarting the catalog with the new environment.

The index exposes metadata through its discovery and query interfaces. It has no per-participant read authorization. Store only metadata approved for this public demonstration.

The deployment uses one catalog host and has no browser publisher. It does not connect to external participant storage or identity infrastructure. Those systems can remain part of a broader project architecture, but they are outside the path established by this repository.
