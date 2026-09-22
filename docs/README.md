# Documentation guide

## Understand and present

- [Illustrated architecture and workflow](workflow.html) — two interactive views: publishing and the shared-asset submodel scenario. Open the downloaded HTML in a browser; it works offline and sends no requests.
- [Architecture](ARCHITECTURE.md) — responsibilities, ownership, replacement and combined discovery.
- [Live demo](LIVE_DEMO.md) — original BIM/AAS presentation steps and expected results.
- [AAS/DPP scenario](AAS_DPP_SCENARIO.md) — mapping decisions and the plan for the group's earlier data.

## Run it

- [Individual publisher setup](../publisher/README.md) — each participant's local dummy sender.
- [Deploy the central catalog](DEPLOYMENT.md) — server information, secrets, HTTPS, persistence and updates.
- [Local catalog development](../catalog/README.md) — local stack and development commands.
- [Original fixtures](../demo-data/README.md) — two publishers, replacement and invalid submissions.
- [Shared-asset fixtures](../demo-data/aas-dpp/README.md) — three synthetic submodel contributions and a query.

## Integrate and verify

- [HTTP ingestion contract](HTTP_INGESTION_CONTRACT.md) — request formats and responses.
- [SPARQL](SPARQL.md) — query API, examples and restrictions.
- [Requirements](REQUIREMENTS.md) — intended demo behavior.
- [External acceptance checklist](EXTERNAL_TESTS.md) — final deployment checks.
- [Implementation audit](AUDIT.md) — scope, limitations and what tests establish.

The central catalog receives metadata; the publisher runs separately. This repository simulates an EDC-side HTTP sender, not Eclipse EDC/DSP. All indexed metadata is publicly readable. Synthetic examples and plans for real AAS/DPP data are explicitly distinguished.
