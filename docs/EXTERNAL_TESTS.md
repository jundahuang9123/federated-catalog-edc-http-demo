# Deployment acceptance checklist

These checks establish what was observed on a particular server. Keep credentials out of the completed record.

## Record the deployment

| Field | Observed value |
| --- | --- |
| Repository URL | pending |
| Commit | pending |
| Test/CI result URL | pending |
| Server OS and architecture | pending |
| Docker and Compose versions | pending |
| Catalog HTTPS origin | pending |
| Test date and operator | pending |
| Backup/restore test reference | pending |

## Configuration and network

- [ ] `python3 scripts/check_config.py` succeeds without printing secrets.
- [ ] `docker compose config --quiet` succeeds.
- [ ] `EDC_DEMO_PARTICIPANTS` contains at least two participant URIs with different 64-or-more-character hexadecimal tokens.
- [ ] Only the catalog DNS name is required; no publisher hostname is configured.
- [ ] The browser trusts the HTTPS certificate and HTTP redirects to HTTPS.
- [ ] The public server exposes 80/443 as intended and does not expose catalog port 8000 or Fuseki port 3030.
- [ ] `.env` permissions and backup location follow the institution's secret-handling rules.
- [ ] `GET /health` and `GET /ready` return 200.
- [ ] `GET /status` reports `mode: http-demo`, the expected participant count and ready dependencies.

## Ingestion and isolation

Start from a fresh index for exact counts, or record the starting graph and dataset counts.

- [ ] Simulator A publishes `demo-data/participant-a/catalog-v1.ttl` over HTTPS and receives participant A plus A's graph ID.
- [ ] Simulator B publishes `demo-data/participant-b/catalog-v1.ttl` and receives participant B plus a different graph ID.
- [ ] Discovery shows A's two v1 datasets and B's one dataset.
- [ ] Dataset provider values come from authenticated graph ownership.
- [ ] Publishing A v2 removes A's old Floor package, adds Envelope package and keeps B unchanged.
- [ ] Repeating one accepted snapshot does not create another participant graph.
- [ ] An invalid bearer token receives 401 and creates no graph.
- [ ] The invalid RDF fixture receives 422 at `stage: validation` and leaves A's last valid snapshot intact.
- [ ] An unsupported media type receives 415.
- [ ] A payload above the configured bound is rejected.
- [ ] Application responses include a request ID that can be correlated with sanitized server logs.

## Discovery and query

- [ ] `GET /datasets` returns the expected entries.
- [ ] `GET /datasets/detail` returns triples and the correct participant for one A and one B dataset.
- [ ] `datasets.rq` returns datasets from both named graphs.
- [ ] `participants.rq` shows the two graph IDs.
- [ ] `walls.rq` returns two results before A v2 and three after A v2 on a fresh index.
- [ ] `ask.rq` returns true.
- [ ] SPARQL Update, `SERVICE` and `FROM` requests are rejected.

## Persistence and operations

- [ ] `docker compose down` followed by `docker compose up -d` retains both accepted snapshots.
- [ ] `/ready` becomes healthy again after the restart.
- [ ] A stopped-volume backup has been restored successfully into a separate Compose project.
- [ ] Catalog, Fuseki and Caddy logs contain no bearer tokens or Fuseki password.
- [ ] The operator knows that `docker compose down --volumes` removes the index and Caddy state.
- [ ] The deployed image versions and commit are recorded for the presentation.

## Claim review

- [ ] The UI, repository description and presentation call this an **EDC HTTP adapter simulation** or **HTTP ingestion boundary demo**.
- [ ] The presentation explicitly states that no Eclipse EDC runtime or DSP exchange is executed.
- [ ] No evidence is described as contract negotiation, policy enforcement, control-plane behavior or data-plane transfer.
- [ ] Cross-participant queries are described as queries over a central materialized Fuseki dataset, not distributed federation.
- [ ] Only approved public demo metadata is stored.

Passing this checklist supports the HTTP/DCAT boundary claim. It does not certify interoperability with Eclipse EDC or any dataspace protocol.
