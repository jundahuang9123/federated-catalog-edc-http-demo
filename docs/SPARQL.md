# Query the catalog over HTTP

Anyone who can reach the deployed catalog can submit a read-only SPARQL query over HTTPS. No publisher token is needed to read the public metadata. Send a JSON object with one non-empty `query` string to `POST /sparql`:

```http
POST /sparql
Content-Type: application/json

{"query":"SELECT ..."}
```

The response is [SPARQL Results JSON](https://www.w3.org/TR/sparql11-results-json/). A `SELECT` response has `head.vars` and `results.bindings`; an `ASK` response has a `boolean` value. Each binding identifies its RDF term type and value. The catalog's browser editor uses the same endpoint as a remote client.

Use `GRAPH ?graph { ... }` when querying publisher contributions. The catalog stores each publisher's current catalog in its own named graph. A query can read all of those graphs and join resources that share identifiers, while the `?graph` result preserves where each statement came from. This is one central query service; it does not contact other publishers when answering.

## Quick remote request

Replace the hostname with the deployed catalog domain. This request lists datasets and their source graphs:

```bash
curl --fail-with-body --show-error --silent \
  'https://<CATALOG_HOST>/sparql' \
  -H 'Content-Type: application/json' \
  --data-binary '{"query":"PREFIX dcat: <http://www.w3.org/ns/dcat#> SELECT ?graph ?dataset WHERE { GRAPH ?graph { ?dataset a dcat:Dataset } } ORDER BY ?graph ?dataset"}'
```

For a populated catalog, the response has this shape (identifiers and row count depend on what has been published):

```json
{
  "head": {"vars": ["graph", "dataset"]},
  "results": {"bindings": [
    {
      "graph": {"type": "uri", "value": "urn:catalog:urn%3Ademo%3Aparticipant%3Aa"},
      "dataset": {"type": "uri", "value": "urn:example:dataset"}
    }
  ]}
}
```

An empty catalog returns an empty `bindings` array. `ASK` queries return `{"head": {}, "boolean": true}` or `false`. The endpoint accepts JSON `POST` requests; `GET ?query=...` and a raw `application/sparql-query` body are not implemented.

## Run a query file

```bash
python3 - <<'PY' > /tmp/catalog-query.json
import json
from pathlib import Path

print(json.dumps({"query": Path("demo-data/queries/datasets.rq").read_text()}))
PY

curl --fail \
  -H 'Content-Type: application/json' \
  --data-binary @/tmp/catalog-query.json \
  https://<CATALOG_HOST>/sparql
```

Ready-to-use queries are in `demo-data/queries/`:

- `datasets.rq` lists DCAT datasets with their named graph and title;
- `participants.rq` lists participant graph IDs;
- `walls.rq` finds BIM and AAS datasets linked to the IFC wall class;
- `ask.rq` checks whether any DCAT dataset exists.

The group AAS example also includes [submodels.rq](../demo-data/group-aas/submodels.rq), which returns its discoverable submodels, optional asset and shell links, source graph, semantic type and access URL. These results are metadata references; the AAS content itself remains at the source API.

For simpler remote discovery without writing SPARQL, use the public [catalog and dataset endpoints](DISCOVERY.md).

## Restrictions

The endpoint accepts SELECT and ASK only. It rejects:

- SPARQL Update forms;
- `SERVICE` remote requests;
- `FROM` and `FROM NAMED` dataset clauses;
- extension function calls;
- malformed JSON or a missing `query` string.

The service adds an outer row limit to SELECT and bounds request bytes, response bytes, execution time and concurrent queries. Configure these limits with:

| Setting | Default |
| --- | --- |
| `SPARQL_MAX_REQUEST_BYTES` | 32768 |
| `SPARQL_MAX_ROWS` | 500 |
| `SPARQL_MAX_RESPONSE_BYTES` | 2097152 |
| `SPARQL_TIMEOUT_SECONDS` | 10 |

Two queries can execute at once; an additional concurrent request receives HTTP 429. Invalid queries or disallowed forms receive 400; an oversized request receives 413; a timeout receives 504; an unavailable index or oversized response receives 502. The endpoint is public, so publish only metadata approved for public reading. The publisher token grants write access to one publisher's graph; it is not a read credential.

## Meaning of “federated” here

Each authenticated participant owns a separate named graph, and one query can inspect several of those graphs. All graphs are stored in one central Fuseki dataset. The endpoint does not send subqueries to remote SPARQL services, so it should not be described as distributed SPARQL federation.
