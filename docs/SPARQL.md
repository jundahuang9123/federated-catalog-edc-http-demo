# Read-only SPARQL

The catalog exposes bounded SELECT and ASK queries at:

```http
POST /sparql
Content-Type: application/json

{"query":"SELECT ..."}
```

Results use the standard SPARQL JSON shape returned by Fuseki. The catalog UI provides an editor and displays SELECT bindings or an ASK boolean.

## Example

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

This interface intentionally reads the materialized catalog index without per-participant authorization. Do not ingest confidential metadata.

## Meaning of “federated” here

Each authenticated participant owns a separate named graph, and one query can inspect several of those graphs. All graphs are stored in one central Fuseki dataset. The endpoint does not send subqueries to remote SPARQL services, so it should not be described as distributed SPARQL federation.
