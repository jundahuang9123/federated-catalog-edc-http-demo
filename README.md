# Federated Catalog — EDC HTTP Boundary Demo

This repository demonstrates a federated catalog accepting DCAT/RDF snapshots over an authenticated HTTP boundary. An individually runnable browser publisher and a command-line simulator act as the last step of a hypothetical EDC-side adapter: they send a participant credential with `POST /catalog`.

**Scope:** the simulator proves the HTTP/DCAT ingestion boundary that an EDC-side adapter could call. It does not implement Eclipse EDC, Dataspace Protocol (DSP), contract negotiation, policy enforcement, an EDC control plane, or an EDC data plane. The bearer tokens are demo credentials configured by the catalog operator; they are not EDC or DSP credentials.

```text
EDC HTTP adapter simulator
  -- Bearer token + DCAT/RDF -->  POST /catalog
                                      |
                                   Caddy HTTPS
                                      |
                               FastAPI catalog
                          auth -> SHACL -> graph PUT
                                      |
                              Fuseki / persistent TDB2
                                      |
                     discovery API, UI and read-only SPARQL
```

The deployed service needs one DNS name. Each participant can run the optional dummy publisher locally; it needs no domain or inbound internet port. The command-line simulator is also available.

## A catalog of catalogs

Each dummy publisher owns **one catalog snapshot**. Every successful push replaces that publisher’s entire previous snapshot, including removing datasets omitted from the new version. Changing the catalog IRI does not create a second catalog for that publisher. Other publishers are untouched.

The federated catalog lists the contributed catalogs and searches their datasets together. Each publisher retains a separate named graph and every dataset result retains its publisher and catalog. Shared RDF identifiers allow SPARQL joins; contributions are not silently merged. All metadata is publicly readable.

- `GET /catalogs` lists published catalogs, their publishers and dataset counts.
- `GET /datasets?q=wall` searches across dataset titles, descriptions, keywords, identifiers and sources (case-insensitive substring matching).
- `GET /datasets/detail?dataset_id=...&graph=...` reads a dataset from its source graph. Use the graph returned with the dataset; omitting it returns HTTP 409 if the identifier occurs in several sources.
- The browser provides a catalog list, combined dataset search and a SPARQL editor. `POST /sparql` accepts read-only SELECT/ASK queries across the stored graphs.

A push must contain exactly one `dcat:Catalog` with an IRI and link all its datasets using `dcat:dataset`, optionally through dataset series. A valid catalog with no datasets clears that publisher’s old dataset listings. A malformed or rejected push preserves the previous snapshot.

## What the demo shows

- A configured token identifies one simulated participant.
- The catalog derives graph ownership from that token. Client-supplied participant headers do not control graph ownership.
- Valid RDF is checked against the catalog SHACL shapes and stored in one named graph per participant.
- A later successful submission replaces that participant's snapshot while leaving other participants unchanged.
- Discovery and bounded read-only SPARQL query all participant graphs in the materialized index.
- Fuseki data survives an ordinary `docker compose down` and `docker compose up -d` cycle.

Only public demonstration metadata belongs in this catalog. Discovery and query results are intentionally readable without per-dataset authorization.

## Repository layout

- `publisher/` — standalone local browser sender for individual testing and demos; no EDC runtime.
- `catalog/` — FastAPI ingestion, validation, discovery, UI and Fuseki client.
- `scripts/edc_http_simulator.py` — command-line client for the simulated EDC adapter boundary.
- `demo-data/` — two participant snapshots, an invalid payload and SPARQL examples.
- `deploy/` — Caddy and Fuseki configuration.
- `docker-compose.yml` — single-host HTTPS deployment with persistent Fuseki storage.
- `docs/` — contract, architecture, deployment and demonstration runbooks.

## Deploy on the demo server

Prerequisites are one Linux server with Docker Compose v2, one DNS record pointing to it, and inbound ports 80/443. Then:

```bash
git clone <this-repository-url>
cd federated-catalog-edc-http-demo
cp .env.example .env

# Edit .env. Generate independent secrets with:
openssl rand -hex 32

python3 scripts/check_config.py
docker compose config --quiet
docker compose up -d --build
```

Set `CATALOG_HOST` to the one catalog hostname. Set `EDC_DEMO_PARTICIPANTS` to a JSON object that maps at least two participant URIs to different tokens of 64 or more hexadecimal characters. Keep `.env` out of Git.

Verify the deployment:

```bash
curl --fail https://<CATALOG_HOST>/health
curl --fail https://<CATALOG_HOST>/ready
```

The UI is at `https://<CATALOG_HOST>/`.

## Start your individual dummy publisher

After obtaining this repository (or just its `publisher/` folder), run with Python 3.11+:

```bash
python3 publisher/server.py
```

Open http://127.0.0.1:8787, enter the catalog URL and **your own token**, choose a DCAT file and publish. No Python dependencies or publisher domain are needed. The catalog operator must provision your token first. This is a testing/demo HTTP sender, not an Eclipse EDC connector.

See [individual setup, Docker alternative and usage](publisher/README.md).

## Send the first two snapshots with the CLI

The simulator reads the token for `--participant` from `EDC_DEMO_PARTICIPANTS` in `.env` and never prints it.

```bash
python3 scripts/edc_http_simulator.py \
  --catalog-url https://<CATALOG_HOST>/catalog \
  --participant urn:demo:participant:a \
  --rdf demo-data/participant-a/catalog-v1.ttl

python3 scripts/edc_http_simulator.py \
  --catalog-url https://<CATALOG_HOST>/catalog \
  --participant urn:demo:participant:b \
  --rdf demo-data/participant-b/catalog-v1.ttl
```

An accepted response identifies the authenticated participant, assigned graph and request ID. Open the UI or request `GET /datasets` to show both participants' metadata.

To demonstrate replacement, send `demo-data/participant-a/catalog-v2.ttl` with participant A's credential. To demonstrate rejection without losing the last valid snapshot, send `demo-data/invalid/invalid-catalog.ttl`.

See [the complete live demo](docs/LIVE_DEMO.md) and [the HTTP ingestion contract](docs/HTTP_INGESTION_CONTRACT.md).

## Validate the repository

```bash
python3 -m venv .venv
.venv/bin/pip install -c catalog/constraints.txt -e './catalog[dev]'
(cd catalog && ../.venv/bin/pytest -q)
.venv/bin/python -m unittest scripts.test_edc_http_simulator
.venv/bin/python -m unittest discover -s publisher -p 'test_*.py'

# Requires a running Docker engine and uses an isolated disposable project.
.venv/bin/python scripts/integration_test.py
```

## Documentation

- [HTTP ingestion contract](docs/HTTP_INGESTION_CONTRACT.md)
- [Architecture and trust boundary](docs/ARCHITECTURE.md)
- [Server deployment](docs/DEPLOYMENT.md)
- [Live demonstration](docs/LIVE_DEMO.md)
- [Read-only SPARQL](docs/SPARQL.md)
- [Acceptance checklist](docs/EXTERNAL_TESTS.md)
- [Demo requirements](docs/REQUIREMENTS.md)

## Attribution

This fork starts from [solid-federated-catalog-demo](https://github.com/jundahuang9123/solid-federated-catalog-demo) at commit `a76d422`, whose catalog derives from [Dual-Federated-Catalog-Solid-EDC-](https://github.com/jundahuang9123/Dual-Federated-Catalog-Solid-EDC-). It retains the component `LICENSE`, `NOTICE` and `CREDITS` files. The fixtures use the [ConstructDCAT](https://github.com/jundahuang9123/ConstructDCAT) vocabulary, version 0.1.0, commit `2effb755897b99342f8405afac96425f6c13649c` (Junda Huang, CC BY 4.0).
