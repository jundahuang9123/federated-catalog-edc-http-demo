# Deployment and server handover

## Target topology

One Linux server runs three containers:

```text
Internet :80/:443 -> Caddy -> FastAPI catalog -> Fuseki/TDB2 volume
```

The deployment needs one DNS name for the catalog. Caddy obtains and renews the HTTPS certificate. FastAPI and Fuseki have no published host ports.

This stack demonstrates a custom HTTP ingestion boundary. It does not install or connect an Eclipse EDC control plane or data plane and does not perform DSP negotiation, contract agreement, transfer orchestration, or policy enforcement.

## Information to obtain from the supervisor

- server IP address, SSH user and permitted authentication method;
- Linux distribution and CPU architecture;
- Docker Engine and Docker Compose v2 availability;
- one DNS A record, and an AAAA record only if IPv6 reaches the server;
- permission for inbound TCP 80 and 443;
- outbound access to the configured container registries;
- backup location and operational owner.

A small demonstration can start with 2 vCPUs, 4 GB RAM and 20 GB persistent disk, then be adjusted from measurement. This is a planning estimate rather than a capacity guarantee.

The provided Caddy configuration expects to manage HTTPS directly at a hostname. An institutional reverse proxy, private-only DNS, a URL subpath, or a server without Docker requires a deployment-specific adaptation.

## Configure the environment

```bash
git clone <this-repository-url>
cd federated-catalog-edc-http-demo
cp .env.example .env
chmod 600 .env
```

Generate the Fuseki password and each participant token independently:

```bash
openssl rand -hex 32
```

Paste the values into `.env`. The participant configuration is one JSON object on one line:

```dotenv
EDC_DEMO_PARTICIPANTS={"urn:demo:participant:a":"<token-a>","urn:demo:participant:b":"<token-b>"}
```

Each production demo token must contain at least 32 random bytes encoded as 64 or more hexadecimal characters, and each participant must have a different token. Participant keys must be URI-shaped identifiers. They can be project URNs; they do not need to resolve on the Web.

| Setting | Purpose |
| --- | --- |
| `CATALOG_HOST` | One DNS hostname, without scheme, port or path |
| `ACME_EMAIL` | Operator contact used by Caddy certificate management |
| `CATALOG_MODE` | Must be `http-demo` |
| `CATALOG_PUBLIC_URL` | `https://` followed by `CATALOG_HOST` |
| `CATALOG_CORS_ORIGINS` | Optional comma-separated HTTPS browser origins; leave empty for both bundled senders |
| `CATALOG_MAX_INGEST_BYTES` | FastAPI request-body limit; default 2 MiB |
| `CATALOG_STARTUP_WAIT_SECONDS` | Time allowed for Fuseki to become reachable |
| `EDC_DEMO_PARTICIPANTS` | JSON mapping participant URI to its private demo bearer token |
| `FUSEKI_PASSWORD` | Independent random hexadecimal admin password |
| `FUSEKI_TIMEOUT_SECONDS` | Internal Fuseki request timeout |
| `SPARQL_*` | Bounds for public read-only queries |

The root Compose file supplies the internal `FUSEKI_URL` as `http://fuseki:3030/catalog`. Do not place tokens or the Fuseki password in Git, screenshots, shell transcripts, issue reports or browser code.

## Validate and start

Run the checks before starting containers:

```bash
python3 scripts/check_config.py
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

The configuration check validates structure and placeholders. It cannot prove DNS, firewall access or certificate issuance.

After Caddy has obtained the certificate:

```bash
curl --fail https://<CATALOG_HOST>/health
curl --fail https://<CATALOG_HOST>/ready
curl --fail https://<CATALOG_HOST>/status
```

- `/health` confirms that the FastAPI process is alive.
- `/ready` returns 200 only when the catalog is operational and its dependencies are ready.
- `/status` reports mode, participant count, graph count, dataset count and dependency state.

The UI is served at `https://<CATALOG_HOST>/`. Do not expose ports 8000 or 3030 through a firewall or extra Compose port mapping.

Remote readers can use the same HTTPS origin for [catalog and dataset search](DISCOVERY.md) or [SPARQL requests](SPARQL.md). These read endpoints are public and need no participant token.

## Run an individual publisher

Give each participant the catalog URL and only their own token. They run `python3 publisher/server.py` locally and enter those details in the browser. See [individual setup](../publisher/README.md). The publisher is not part of the central Compose stack.

## Run the CLI from the operator workstation

Create an ignored `.env.simulator` containing only the participant mapping used by the client:

```dotenv
EDC_DEMO_PARTICIPANTS={"urn:demo:participant:a":"<token-a>","urn:demo:participant:b":"<token-b>"}
```

Then send a snapshot:

```bash
python3 scripts/edc_http_simulator.py \
  --catalog-url https://<CATALOG_HOST>/catalog \
  --participant urn:demo:participant:a \
  --env-file .env.simulator \
  --rdf demo-data/participant-a/catalog-v1.ttl
```

The simulator requires HTTPS for remote hosts. Plain HTTP is permitted only for `localhost` or `127.0.0.1`. See [HTTP_INGESTION_CONTRACT.md](HTTP_INGESTION_CONTRACT.md) for the wire contract.

## Persistence and restart

```bash
docker compose down
docker compose up -d
```

The named `fuseki-data` volume stores `/fuseki`, including TDB2 at `/fuseki/databases/catalog`. Ordinary `down` retains it. `docker compose down --volumes` permanently removes the index and Caddy volumes; use it only when intentionally resetting the demonstration.

Keep the same Compose project name. A different project name creates different named volumes and will look like an empty catalog.

## Token rotation and participant changes

Edit `EDC_DEMO_PARTICIPANTS` in `.env`, then recreate the catalog container:

```bash
python3 scripts/check_config.py
docker compose up -d --force-recreate catalog
```

The old token stops working after the restarted catalog loads the new mapping. Changing a participant URI creates a different graph identity; it does not rename or delete the old graph. Plan identity changes before publishing, or reset the demo index deliberately.

## Logs and troubleshooting

```bash
docker compose logs --tail=100 catalog fuseki reverse-proxy
```

Common cases:

- `401 invalid_credentials`: the bearer token does not match the deployed mapping.
- `415 unsupported_media_type`: use a supported RDF content type or a recognized simulator file extension.
- `422 validation_failed`: inspect the returned validation errors; the last valid graph remains stored.
- `502 store_write_failed`: inspect catalog-to-Fuseki connectivity and credentials.
- `/ready` returns 503: inspect the dependency object and both catalog and Fuseki logs.
- certificate failure: verify DNS, ports 80/443, the hostname and Caddy logs.

## Backup and update

For a small demonstration, take a stopped-volume backup with the institution's Docker-volume backup procedure. Stop writes and Fuseki before copying TDB2 files, and test restoration into a separate Compose project. Store `.env` in restricted backup storage because it contains all demo credentials.

Before updating:

```bash
git pull --ff-only
python3 scripts/check_config.py
docker compose config --quiet
docker compose up -d --build
```

Record the deployed commit and image versions for the presentation. Re-run the acceptance checklist in [EXTERNAL_TESTS.md](EXTERNAL_TESTS.md).

## References

- [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [Apache Jena Fuseki configuration](https://jena.apache.org/documentation/fuseki2/fuseki-configuration.html)
- [Fuseki main server and Shiro security](https://jena.apache.org/documentation/fuseki2/)
