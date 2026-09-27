# Federated catalog — a catalog of publisher catalogs

Each publisher maintains one DCAT catalog. This demo accepts their catalogs over HTTP, keeps their sources separate, and makes the metadata searchable together.

**[Explore the illustrated workflow](docs/workflow.html)** · **[Documentation index](docs/README.md)** · **[AAS/DPP data scenario](docs/AAS_DPP_SCENARIO.md)**

The HTML workflow is a self-contained file: download or open it locally in a browser. GitHub displays its source; the interactive controls are an illustration and do not publish data.

## How it works

1. Each independently running **EDC dummy publisher** sends its complete DCAT/RDF catalog and its own token using `POST /catalog`.
2. The catalog authenticates the publisher, validates the metadata and replaces only that publisher's previous snapshot.
3. Everyone can browse catalogs, search datasets and submit read-only SPARQL queries across the stored metadata.

One publisher has one current catalog. Omitted datasets disappear on replacement; invalid submissions leave the previous snapshot intact. Shared RDF identifiers connect resources without merging source ownership. The actual data files remain with their providers.

This is an **HTTP ingestion demonstration**, not Eclipse EDC or DSP. It does not negotiate contracts, enforce EDC policies, retrieve AAS payloads or assemble a complete DPP. Reads are public; use public demo metadata only.

## Start as a publisher

Obtain this repository or a copy of `publisher/`. With Python 3.11+, from the repository root:

```bash
python3 publisher/server.py
```

Open http://127.0.0.1:8787. Enter the catalog URL and **your own operator-issued token**, choose a DCAT file and publish. No Python dependencies, publisher domain or inbound internet port are needed.

[Individual setup and Docker alternative](publisher/README.md) · [CLI and presentation steps](docs/LIVE_DEMO.md)

## Deploy the central catalog

The operator needs one Linux server, Docker Compose v2, a catalog DNS name and inbound ports 80/443.

```bash
cp .env.example .env
# Configure the hostname and independent secrets in .env.
# Generate each secret separately with: openssl rand -hex 32
python3 scripts/check_config.py
docker compose config --quiet
docker compose up -d --build
```

Open the catalog domain and confirm `/ready` returns HTTP 200. The operator provisions a distinct token per publisher in `EDC_DEMO_PARTICIPANTS`; the catalog does not generate tokens automatically.

[Complete deployment and handover guide](docs/DEPLOYMENT.md)

## Choose a data story

| Scenario | What it shows | Starting point |
| --- | --- | --- |
| BIM + AAS | Different data representations discovered through a common asset **type** | [Original two-publisher fixtures](demo-data/README.md) |
| Linked A + B datasets | B's component and material passports explicitly reference A's frame and floor datasets | [Publisher B linked catalog](demo-data/participant-b/README.md) |
| Group AAS API | Discovery metadata linked to the actual API records, including a DPP template | [Linked source catalog](demo-data/group-aas/README.md) |
| AAS/DPP discovery | Three publishers' submodels describing the same individual **asset** | [Synthetic pump scenario](demo-data/aas-dpp/README.md) |

The new AAS/DPP scenario contains synthetic catalog metadata and placeholder distribution URLs. The supplied group API is now mapped separately: eight asset-linked tracking instances and five unlinked templates in the captured snapshot. [Mapping plan and next steps](docs/AAS_DPP_SCENARIO.md).

## Interfaces

| Interface | Purpose |
| --- | --- |
| `POST /catalog` | Replace the authenticated publisher's complete catalog |
| `GET /catalogs` | List contributed catalogs and their sources |
| `GET /datasets?q=...` | Search titles, descriptions, keywords, identifiers and sources |
| `GET /datasets/detail?dataset_id=...&graph=...` | Inspect a dataset from a specific source |
| `POST /sparql` | Execute bounded SELECT/ASK queries and return JSON results |
| `/`, `/sparql.html`, `/status.html` | Browse, query and inspect status |

[Public search and discovery API](docs/DISCOVERY.md) · [Remote SPARQL requests](docs/SPARQL.md) · [HTTP publishing contract](docs/HTTP_INGESTION_CONTRACT.md)

## Develop and verify

```bash
python3 -m venv .venv
.venv/bin/pip install -c catalog/constraints.txt -e './catalog[dev]'
(cd catalog && ../.venv/bin/pytest -q)
.venv/bin/python -m unittest scripts.test_edc_http_simulator
.venv/bin/python -m unittest discover -s publisher -p 'test_*.py'
# Requires a running Docker engine; uses an isolated disposable project.
.venv/bin/python scripts/integration_test.py
```

`catalog/` contains the service, `publisher/` the standalone browser sender, `demo-data/` the fixtures, and `deploy/` the server configuration. [Local catalog development](catalog/README.md).

## Attribution

This fork starts from [solid-federated-catalog-demo](https://github.com/jundahuang9123/solid-federated-catalog-demo) at commit `a76d422`, whose catalog derives from [Dual-Federated-Catalog-Solid-EDC-](https://github.com/jundahuang9123/Dual-Federated-Catalog-Solid-EDC-). It retains the component `LICENSE`, `NOTICE` and `CREDITS` files. The fixtures use the [ConstructDCAT](https://github.com/jundahuang9123/ConstructDCAT) vocabulary, version 0.1.0, commit `2effb755897b99342f8405afac96425f6c13649c` (Junda Huang, CC BY 4.0).
