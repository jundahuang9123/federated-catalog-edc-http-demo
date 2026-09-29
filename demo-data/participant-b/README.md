# Publisher B: a catalog explicitly linked to Publisher A

Use [catalog-linked-to-a.ttl](catalog-linked-to-a.ttl) with Publisher A's
[catalog-v1.ttl](../participant-a/catalog-v1.ttl). B contributes one catalog with
two AAS dataset descriptions:

| Publisher B dataset | Related Publisher A dataset | Shared asset type |
| --- | --- | --- |
| Wall component passport | Frame export — revision 1 | `ifc:IfcWall` |
| Floor material passport | Floor package | `ifc:IfcSlab` |

B declares each connection using `dct:relation` and the exact IRI already used
by A. For example:

```turtle
ex:b-components dct:relation ex:a-frame .
```

[Dublin Core relation](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/#relation)
expresses an association with another resource. Here the associations are
synthetic publisher claims. They do not assert that the datasets are identical,
that a specific physical asset has been verified, or that the catalog assembled
a complete AAS or DPP. The distribution URLs are placeholders; the file contains
discovery metadata, not actual AAS submodel JSON.

For the partner presentation, [catalog-connector-demo.ttl](catalog-connector-demo.ttl)
contains the same two datasets inside Building passports → Wall passports
groups. Both files advertise B’s DID and DSP endpoint and include per-dataset
Asset-ID values. See [the connector demo guide](../../docs/CONNECTOR_DEMO.md)
for the mapping, interactive graph and deployment steps. The query below
works with either flat or nested B membership.

## Publish B

From the repository root on the catalog server, select B's token from the
existing `.env`. Replace `<CATALOG_HOST>` with the deployed hostname:

```bash
python3 scripts/edc_http_simulator.py \
  --catalog-url https://<CATALOG_HOST>/catalog \
  --participant urn:demo:participant:b \
  --env-file .env \
  --rdf demo-data/participant-b/catalog-linked-to-a.ttl
```

For an independently running [browser publisher](../../publisher/README.md),
give its operator only B's token and the `/catalog` URL, and choose this Turtle
file. The catalog server's complete `.env` is not a publisher handover file.

This publication replaces B's previous snapshot, if any. A's snapshot is
unchanged. With A v1 and this B snapshot, discovery shows **two catalogs and
four datasets**. Searching `frame` or `floor` finds both the relevant A record
and B's passport metadata because B includes matching titles, descriptions and
keywords. Keyword search does not traverse RDF relations.

## Query the connections

Copy [publisher-links.rq](../queries/publisher-links.rq) into the catalog's
SPARQL editor and run it. The query follows the relation from B's graph into A's
graph and returns these two pairs, including both source graphs, catalogs and
dataset IRIs:

| A title | B title |
| --- | --- |
| Frame export — revision 1 | Wall component passport |
| Floor package | Floor material passport |

The query needs both referenced A datasets to exist. If A later publishes
`catalog-v2.ttl`, its floor dataset is removed: B's floor relation remains in B's
metadata, but the joined query returns only the frame/passport pair. A normal
dataset listing still shows all current B records. This demonstrates that an
independent publisher's update does not silently edit another source.

The original [catalog-v1.ttl](catalog-v1.ttl) remains the smaller, one-dataset B
fixture used for the original demo counts. Choose one B snapshot at a time.
