# Implementation audit

## Review target

This fork narrows the earlier multi-mode catalog and browser publisher demonstrator to one deployable path:

```text
simulated EDC-side HTTP adapter -> POST /catalog -> validation -> Fuseki
```

The audit standard is the claim in [REQUIREMENTS.md](REQUIREMENTS.md). The tool demonstrates the final HTTP/DCAT ingestion boundary only. Eclipse EDC, DSP, negotiation, policy enforcement, and EDC control/data planes remain outside the implementation and must not be inferred from a successful request.

## Architecture decisions

- The only catalog mode is `http-demo`.
- The deployed stack uses one `CATALOG_HOST`; no publisher hostname is required.
- `EDC_DEMO_PARTICIPANTS` is an explicit participant URI to demo-token mapping.
- The bearer token determines the participant. The reverse proxy strips caller-supplied participant identity headers.
- The named graph is derived from the authenticated participant URI.
- SHACL validation precedes storage.
- Graph Store `PUT` replaces one participant graph without a preceding delete.
- Discovery derives provider identity from graph ownership rather than untrusted RDF statements.
- Fuseki has a persistent volume and no public port or SPARQL Update service.
- Public SPARQL is restricted to bounded SELECT and ASK.
- The senders are a standalone local browser publisher and a CLI simulator, both explicitly labelled as non-EDC dummies.

## Security and trust findings

The configured tokens are shared demo secrets. Production configuration validation requires at least two unique values with 32 random bytes represented as hexadecimal. Tokens do not carry claims, prove an EDC participant context, or convey contract/policy evidence. Compromise of one token permits replacement of that participant's catalog graph until the credential is rotated.

Graph isolation does not depend on `dct:publisher` in the submitted RDF. The public proxy removes caller-supplied participant identity headers, and the application rejects a conflicting identity header if reached directly. Fuseki credentials remain on the server. Each publisher holds only its own token; the full participant mapping belongs to the operator.

Discovery and query are publicly readable in the supplied topology. This is suitable for approved public demo metadata and unsuitable for confidential participant data without an added read-authorization design.

The catalog has no revision preconditions or replay protection. Repeating a snapshot replaces the same graph; two different concurrent writes for one participant use last-committed-write semantics. A future production protocol would need explicit versioning and stronger service identity.

## Verification surfaces

The repository contains automated checks for:

- participant configuration parsing and production guards;
- correct token authentication and generic credential failures;
- spoofed participant-header rejection at the application boundary;
- valid publication, graph replacement and cross-participant isolation;
- RDF/media-type/SHACL failures preserving prior state;
- store failure responses;
- discovery provider identity derived from named graphs;
- bounded read-only SPARQL behavior;
- simulator request headers, body, HTTPS policy and token handling;
- root Compose integration with real Fuseki and persistence.

Before presenting a particular deployment, record the tested commit, automated test results, Compose validation, server architecture, deployed URLs and the live checks in [EXTERNAL_TESTS.md](EXTERNAL_TESTS.md). Unit tests alone do not verify DNS, Caddy certificate issuance, firewall rules, remote reachability or backup restoration.

## Residual limitations

- The adapter is simulated; it is not connected to a real Eclipse EDC event or extension point.
- The participant/token mapping is static until the catalog restarts.
- Tokens are symmetric bearer credentials with no expiration or automatic rotation.
- The index has no metadata read authorization.
- The ingestion API accepts complete snapshots only; it has no patch, version or conflict protocol.
- Querying occurs inside one central Fuseki dataset and does not contact participant endpoints.
- Availability, capacity and backup objectives require measurement and institutional operations on the final server.

These limits are acceptable for the stated demonstrator when they are shown with it rather than hidden behind an “EDC integration” label.
