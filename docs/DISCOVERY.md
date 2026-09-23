# Read the public catalog over HTTP

The deployed catalog exposes its combined metadata to remote readers over HTTPS. Reading needs no token; the participant token is only for replacing that participant's catalog. Use the catalog's public hostname in the examples below.

| Request | Result |
| --- | --- |
| `GET /catalogs` | The current catalog from each publisher, with its catalog IRI, source graph, publisher ID, title and dataset count |
| `GET /datasets` | Dataset listings from all published catalogs |
| `GET /datasets?q=term` | Listings whose identifier, title, description, keyword, publisher or catalog matches `term` |
| `GET /datasets/detail?dataset_id=...&graph=...` | One dataset's RDF statements, types, publisher and source catalog |
| `POST /sparql` | Read-only SELECT or ASK results across the named graphs; see [SPARQL examples](SPARQL.md) |

## Browse and search

```bash
curl --fail-with-body --show-error --silent 'https://<CATALOG_HOST>/catalogs'
curl --fail-with-body --show-error --silent \
  --get --data-urlencode 'q=DPP-EU' \
  'https://<CATALOG_HOST>/datasets'
```

Both listing endpoints return JSON arrays. A dataset listing includes `dataset_id`, `title`, `provider`, `type` and `metadata`. The `metadata.graph` and `metadata.catalog_id` fields identify its source. The same dataset IRI can appear in more than one publisher graph; those are separate listings. `q` is case-insensitive substring matching over the combined listings, not ranked full-text search. An empty query lists all datasets.

To inspect one listing, pass **both** its `dataset_id` and `metadata.graph` from `/datasets`:

```bash
curl --fail-with-body --show-error --silent --get \
  --data-urlencode 'dataset_id=<dataset-id-from-listing>' \
  --data-urlencode 'graph=<graph-from-listing>' \
  'https://<CATALOG_HOST>/datasets/detail'
```

The detail response adds `types` and `triples`; its `provider` comes from the authenticated publisher's graph identity. A missing dataset returns 404. If the same dataset IRI exists in multiple publisher graphs and `graph` is omitted, the service returns 409 so that descriptions from different sources are not mixed.

## What the results represent

Each publisher maintains one current DCAT catalog. Its next accepted `POST /catalog` replaces only its own earlier catalog snapshot. Search and SPARQL combine the **metadata** from all current snapshots, while source graphs remain distinct. A shared asset identifier or explicit RDF link can connect records from different publishers; matching words alone do not establish that two datasets describe the same asset.

The catalog can point to data held elsewhere through a dataset's `dcat:Distribution` and `dcat:accessURL` or `dcat:downloadURL`. Selecting **Open source data** in the browser follows such a link to the provider; the catalog does not proxy or copy the underlying payload. The [group AAS API example](../demo-data/group-aas/README.md) maps actual submodel identifiers, asset and shell links, and source JSON URLs into ConstructDCAT discovery metadata. Its captured eight tracking instances describe eight different assets; its five templates have no observed asset association.

The public catalog does not enforce read permissions. Publish only metadata approved for public access. For write credentials, validation and snapshot replacement, see the [HTTP ingestion contract](HTTP_INGESTION_CONTRACT.md).
