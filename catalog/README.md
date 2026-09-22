# Federated catalog service

This FastAPI service accepts authenticated DCAT/RDF snapshots, validates them with SHACL, replaces one named graph per participant in Fuseki, and exposes discovery, UI and read-only SPARQL interfaces.

The active mode is `http-demo`. It is the server side of the repository's EDC HTTP adapter simulation. It does not implement Eclipse EDC, DSP, contract negotiation, policy enforcement, or EDC control/data planes.

## Local stack

From this directory:

```bash
docker compose up --build
```

Local endpoints:

- catalog API and UI: `http://127.0.0.1:8000`
- Fuseki: `http://127.0.0.1:3030` for local diagnosis only

The local Compose file contains fixed, clearly marked development credentials and binds both ports to loopback. The root production Compose file uses `.env`, exposes only Caddy on 80/443, and keeps Fuseki internal.

From the repository root, publish with one of the local participant tokens declared in `catalog/docker-compose.yaml`:

```bash
EDC_SIMULATOR_TOKEN='<local-participant-a-token>' \
python3 scripts/edc_http_simulator.py \
  --catalog-url http://127.0.0.1:8000/catalog \
  --rdf demo-data/participant-a/catalog-v1.ttl
```

The simulator permits plain HTTP only for localhost.

## Production configuration

The essential settings are:

```dotenv
CATALOG_MODE=http-demo
EDC_DEMO_PARTICIPANTS={"urn:demo:participant:a":"<token-a>","urn:demo:participant:b":"<token-b>"}
FUSEKI_URL=http://fuseki:3030/catalog
FUSEKI_USER=admin
FUSEKI_PASSWORD=<random-password>
```

`EDC_DEMO_PARTICIPANTS` maps participant URIs to demo bearer tokens. Production deployment validation requires at least two unique tokens, each encoded as 64 or more hexadecimal characters. The matched token determines graph ownership; RDF publisher statements and request identity headers do not.

See the root [deployment guide](../docs/DEPLOYMENT.md) for every setting and the [HTTP ingestion contract](../docs/HTTP_INGESTION_CONTRACT.md) for request and response details.

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `POST /catalog` | Authenticate, validate and replace a participant snapshot |
| `GET /catalogs` | List contributed catalogs and publishers |
| `GET /datasets?q=...` | Search datasets across source catalogs |
| `GET /datasets/detail?dataset_id=...&graph=...` | Return dataset metadata and triples |
| `POST /sparql` | Run a bounded SELECT or ASK query |
| `GET /status` | Report counts and dependency state |
| `GET /health` | Process liveness |
| `GET /ready` | Catalog and dependency readiness |
| `GET /` | Browser UI |

Accepted snapshots are stored at `urn:catalog:<percent-encoded-participant-URI>`. A later accepted request for the same participant replaces that complete graph with Graph Store `PUT`. A validation failure leaves the prior snapshot unchanged.

## Develop and test

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -c catalog/constraints.txt -e './catalog[dev]'
(cd catalog && ../.venv/bin/pytest -q)
(cd catalog && ../.venv/bin/ruff check .)
```

Unit tests use in-memory HTTP transports and RDF query fixtures. The root integration test requires Docker and exercises the real catalog/Fuseki path and persistence:

```bash
.venv/bin/python scripts/integration_test.py
```

## Operational behavior

`/ready` reports Fuseki and participant configuration separately. Catalog startup waits for Fuseki for the configured interval. Publication returns structured stages for authentication, parsing, validation and storage failures.

The public query endpoint reads all indexed metadata. Use only metadata approved for public demonstration. The query endpoint operates over one materialized Fuseki dataset; it is not distributed SPARQL federation.
