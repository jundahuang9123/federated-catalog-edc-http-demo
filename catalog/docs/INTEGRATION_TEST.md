# Catalog integration test

The root integration test starts an isolated catalog and a real Fuseki/TDB2 dataset, publishes DCAT/RDF as two configured participants, checks replacement and rejection behavior, recreates the services, and verifies persistence.

It tests the custom HTTP/DCAT boundary used by the EDC adapter simulator. It does not start Eclipse EDC or test DSP, negotiation, policy enforcement, or EDC control/data planes.

## Run

From the repository root with Docker running:

```bash
python3 scripts/integration_test.py
```

The script uses `docker-compose.integration.yml` under an isolated Compose project name and cleans up its disposable containers and volumes. It does not use the production `.env` or production data volume.

## Covered behavior

- catalog and Fuseki readiness;
- accepted participant A and B publications with bearer credentials;
- separate deterministic participant graphs;
- discovery across both graphs;
- participant A snapshot replacement without changing B;
- invalid RDF preserving the previous valid graph;
- unknown-token rejection;
- bounded read-only SPARQL results;
- persistence after container recreation.

For a server deployment, also complete the root [acceptance checklist](../../docs/EXTERNAL_TESTS.md). Local integration does not verify DNS, Caddy certificate issuance, firewall rules or backup restoration.
