# Demo requirements

## Objective

Deploy a persistent federated metadata catalog and demonstrate the HTTP boundary through which an adapter associated with an EDC participant could submit a DCAT/RDF snapshot.

The result must make one claim only: authenticated DCAT/RDF can cross the demonstrated HTTP boundary, be validated, stored under the authenticated participant's graph, and become discoverable in the central index.

## Scope

The repository includes:

- a FastAPI catalog API and browser UI;
- SHACL validation of submitted RDF;
- one replaceable named graph per configured participant;
- a persistent Fuseki/TDB2 index;
- discovery APIs and bounded read-only SPARQL;
- an individually runnable browser publisher and a command-line EDC HTTP adapter simulator;
- a single-host Caddy HTTPS deployment;
- original two-participant fixtures plus a synthetic three-publisher AAS submodel discovery scenario.

The repository does not implement or claim:

- Eclipse EDC runtime behavior;
- Dataspace Protocol communication;
- participant catalog exchange through EDC;
- contract negotiation or contract-agreement verification;
- policy evaluation or enforcement;
- EDC transfer processes, control planes or data planes;
- external participant storage or external identity infrastructure;
- AAS payload assembly or DPP completeness validation;
- authorization for reading indexed metadata;
- distributed SPARQL federation.

## Functional requirements

### HTTP ingestion

- Accept `POST /catalog` with a bearer token and RDF body.
- Support the RDF media types listed in [HTTP_INGESTION_CONTRACT.md](HTTP_INGESTION_CONTRACT.md).
- Return a correlation request ID in accepted and rejected application responses.
- Apply an explicit request-size bound.
- Reject unknown credentials without revealing the participant mapping.

### Identity and isolation

- Configure at least two participant URI/token pairs through `EDC_DEMO_PARTICIPANTS` in production.
- Require unique random tokens containing at least 64 hexadecimal characters.
- Derive participant identity and graph ownership from the token.
- Ignore public caller attempts to assign identity through participant headers.
- Use a deterministic `urn:catalog:<encoded-participant>` graph ID.
- Ensure a publication for one participant cannot replace another participant's graph.

### Validation and storage

- Parse the declared RDF format as UTF-8 and apply the existing SHACL gate.
- Require exactly one IRI-identified catalog linking every included dataset. An empty catalog is valid.
- Do not change storage after authentication, parsing or validation failure.
- Replace a participant snapshot with one Graph Store `PUT`, without a preceding delete.
- Persist Fuseki data across ordinary container recreation.
- Keep Fuseki off public host ports.

### Discovery and query

- List source catalogs and search datasets across participant graphs.
- Preserve source identity when several publishers use the same resource IRI.
- Return dataset detail and the participant derived from graph ownership.
- Report dependency and catalog counts through status/readiness endpoints.
- Permit bounded SELECT and ASK over the materialized index.
- Reject update, remote service and caller-selected dataset operations.

### Simulator

- Select a token from `.env` by participant URI, or accept one through a dedicated process environment variable.
- Send the original RDF bytes with the correct media type and a generated request ID.
- Never print the bearer token.
- Require HTTPS for remote catalogs and permit HTTP only for localhost testing.
- Exit unsuccessfully for HTTP rejection, network failure or invalid local configuration.
- Display a clear disclaimer that it simulates only the HTTP adapter boundary.

### Deployment

- Use one `CATALOG_HOST` and one public HTTPS origin.
- Publish only ports 80/443 through Caddy.
- Validate placeholder, password and participant settings before deployment.
- Store secrets only in an ignored `.env` or an external secret-management mechanism.
- Provide runbooks for startup, backup, live demonstration and acceptance.

## Acceptance scenarios

On a fresh index:

1. participant A publishes v1 and two datasets become discoverable;
2. participant B publishes v1 and one additional dataset appears in a separate graph;
3. the construction wall query returns results from both participants;
4. participant A publishes v2, which replaces A v1 while B remains unchanged;
5. invalid RDF returns 422 and preserves A v2;
6. an unknown token returns 401 and creates no graph;
7. a service restart retains accepted data;
8. Fuseki is unreachable from the public network;
9. presentation materials state the simulator's EDC limitations explicitly.

Detailed checks are in [EXTERNAL_TESTS.md](EXTERNAL_TESTS.md).
