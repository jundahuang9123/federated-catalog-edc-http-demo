# Live demonstration script

[Visual introduction](workflow.html) · [Documentation index](README.md)

This runbook covers the original two-source BIM/AAS scenario. For the three-source shared-asset story, use the [AAS/DPP fixture runbook](../demo-data/aas-dpp/README.md).

## State the scope first

Use this wording at the start:

> This demonstration starts at a custom HTTP delivery boundary. The local dummy publisher or command-line tool represents the last step an adapter beside an EDC connector could perform: it sends an authenticated DCAT/RDF snapshot to the federated catalog. It does not run Eclipse EDC or demonstrate DSP, contract negotiation, policy enforcement, a control plane, or a data plane.

Calling the tool an **EDC HTTP adapter simulator** keeps the architectural intention clear without presenting it as an EDC connector.

## Prepare

1. Complete [the acceptance checklist](EXTERNAL_TESTS.md).
2. Confirm `https://<CATALOG_HOST>/ready` returns 200.
3. Put the configured participant mapping in an ignored `.env.simulator` on the presentation machine.
4. Open `https://<CATALOG_HOST>/` in a browser.
5. Keep a terminal in the repository root.
6. Record the deployed commit and whether the Fuseki index is fresh. Exact counts below assume a fresh index containing only these fixtures.

The mapping should contain at least these participant IDs, each with its own token:

```text
urn:demo:participant:a
urn:demo:participant:b
```

Never display the token values during the presentation.

## 1. Show an empty or current catalog

Open the catalog UI and `/status`. Explain that Fuseki is a materialized metadata index. Participant applications remain responsible for producing their DCAT/RDF; this demo begins when an adapter delivers that RDF.

If the index is intentionally fresh, `/status` should report zero graphs and zero datasets. Existing data is acceptable if you record the starting counts and describe the expected changes instead of claiming absolute totals.

## 2. Publish participant A

```bash
python3 scripts/edc_http_simulator.py \
  --catalog-url https://<CATALOG_HOST>/catalog \
  --participant urn:demo:participant:a \
  --env-file .env.simulator \
  --rdf demo-data/participant-a/catalog-v1.ttl
```

Show the accepted response. It includes:

- participant `urn:demo:participant:a`;
- an encoded `urn:catalog:...` graph URI;
- the request ID.

Refresh the UI. A v1 contributes “Frame export — revision 1” and “Floor package”. Explain that the participant comes from the bearer-token mapping, not from an RDF publisher field or request header.

## 3. Publish participant B

```bash
python3 scripts/edc_http_simulator.py \
  --catalog-url https://<CATALOG_HOST>/catalog \
  --participant urn:demo:participant:b \
  --env-file .env.simulator \
  --rdf demo-data/participant-b/catalog-v1.ttl
```

Refresh discovery. “Component passport set” now appears beside A's two datasets. A fresh index has two participant graphs and three datasets.

## 4. Query across participant graphs

Use the SPARQL page in the UI with the examples from `demo-data/queries/`:

- `participants.rq` shows two distinct named graphs;
- `datasets.rq` lists all three datasets and their graph;
- `walls.rq` finds the IFC and AAS descriptions linked by `cx:describesAssetType ifc:IfcWall`;
- `ask.rq` confirms at least one DCAT dataset exists.

Before the update, `walls.rq` returns two datasets on a fresh index. Their titles do not need the word “wall”; the result comes from the shared semantic property. Explain that this query runs over named graphs already materialized in one Fuseki dataset. It is not distributed SPARQL federation.

## 5. Replace A's snapshot

```bash
python3 scripts/edc_http_simulator.py \
  --catalog-url https://<CATALOG_HOST>/catalog \
  --participant urn:demo:participant:a \
  --env-file .env.simulator \
  --rdf demo-data/participant-a/catalog-v2.ttl
```

Refresh the UI:

- frame revision 2 replaces revision 1;
- Floor package disappears;
- Envelope package appears;
- participant B's Component passport set remains.

A fresh index still has three datasets, and `walls.rq` now returns three. This demonstrates participant-scoped snapshot replacement and isolation.

## 6. Reject invalid RDF without losing A v2

```bash
python3 scripts/edc_http_simulator.py \
  --catalog-url https://<CATALOG_HOST>/catalog \
  --participant urn:demo:participant:a \
  --env-file .env.simulator \
  --rdf demo-data/invalid/invalid-catalog.ttl
```

The command exits unsuccessfully and shows HTTP 422 with `stage: validation`. Refresh discovery and re-run the wall query. A's valid v2 graph and B's graph remain unchanged because validation happened before the Graph Store `PUT`.

## 7. Reject an unknown credential

Use a temporary invalid value without displaying any valid token:

```bash
EDC_SIMULATOR_TOKEN=invalid-demo-token \
python3 scripts/edc_http_simulator.py \
  --catalog-url https://<CATALOG_HOST>/catalog \
  --rdf demo-data/participant-a/catalog-v1.ttl
```

The response is HTTP 401 with `stage: auth`. The error does not disclose which participant or token was expected. Confirm that discovery counts have not changed.

## 8. Show persistence

If restarting during the presentation is acceptable:

```bash
docker compose down
docker compose up -d
```

Wait for `/ready`, then refresh the UI. The accepted participant snapshots remain in the `fuseki-data` volume. Do not add `--volumes`.

## Evidence to record

- deployed repository URL and commit;
- catalog HTTPS URL and certificate status;
- timestamp and request IDs;
- authenticated participant IDs and returned graph IDs;
- HTTP status and stage for rejected requests;
- dataset, graph and wall-query counts before and after replacement;
- successful restart persistence check, if performed;
- the explicit scope statement used in the presentation.

Exclude bearer tokens, `.env` contents, Fuseki credentials and private server information from screenshots and reports.

## Individual browser alternative

Run `python3 publisher/server.py` on each participant machine and open http://127.0.0.1:8787. Enter the same deployed catalog URL with a different operator-issued token for each participant. Select the A/B fixtures used above and click Publish. The HTTP contract and graph replacement behavior are identical to the CLI. This is a dummy for individual testing and demos, not a running EDC connector. See [publisher setup](../publisher/README.md).
