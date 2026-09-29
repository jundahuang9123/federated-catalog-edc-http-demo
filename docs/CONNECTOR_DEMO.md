# Present connector-oriented catalog discovery

This scenario makes the HTTP demo's metadata recognizable to partners using
EDC connectors. It adds advertised connector identifiers to the browser and
API, and an expandable DCAT hierarchy. The sender remains the independent
[EDC dummy publisher](../publisher/README.md); it sends a complete RDF snapshot
with `POST /catalog`. No Eclipse EDC instance, DSP exchange, DID resolution,
credential verification, contract negotiation or data transfer is performed.

## Metadata mapping

The values come from the submitted RDF, not the catalog's `.env` or hardcoded
UI labels. The updated A and B fixtures include these fields:

| UI field | RDF source | Example for B |
| --- | --- | --- |
| Provider-DID | Catalog `edc:participantId` starting with `did:` | `did:web:participant-b.example.org` |
| DSP-Endpoint | Catalog `dcat:service` → `dcat:endpointURL` of a service marked `dcat:endpointDescription "dspace:connector"` | `https://participant-b.example.org/dsp/2025-1` |
| Asset-ID | Dataset `edc:id`, falling back to `dct:identifier` | `b-components` |

Here `edc:` means `https://w3id.org/edc/v0.0.1/ns/`. These are the demo adapter's
supported RDF mappings, not a promise to ingest arbitrary EDC JSON-LD catalog
responses or all protocol versions. The EDC-specific participant/asset fields
and the DCAT data service reflect the concepts in the
[Tractus-X EDC catalog walkthrough](https://github.com/eclipse-tractusx/tractusx-edc/blob/main/docs/usage/management-api-walkthrough/04_catalog.md).

```turtle
@prefix edc: <https://w3id.org/edc/v0.0.1/ns/> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix ex: <https://example.org/live-demo/> .

ex:b-catalog edc:participantId "did:web:participant-b.example.org" ;
    dcat:service ex:b-dsp .
ex:b-dsp a dcat:DataService ;
    dcat:endpointDescription "dspace:connector" ;
    dcat:endpointURL <https://participant-b.example.org/dsp/2025-1> .
ex:b-components edc:id "b-components" .
```

This fragment adds properties to an otherwise complete valid catalog; it is
not a standalone publishable snapshot. Use the supplied fixture below.

Provider-DID is an **unverified publisher claim**. The browser's separate
Publisher field is the authenticated participant identity derived from its
token and source graph. Changing the advertised DID cannot change snapshot
ownership. Asset-ID is a connector-local data asset identifier, not proof of
physical asset identity; shared physical asset links still use ConstructDCAT.
The `example.org` DID, endpoint and access URLs are placeholders. The UI does
not send DSP requests to the advertised endpoint.

Missing fields display **Not supplied**; existing catalogs stay valid.
For multiple supplied values, the adapter chooses the first lexical value
(and prefers `edc:id` over `dct:identifier`). All submitted statements remain
available through SPARQL. Re-publish an updated fixture to see new fields on an
already populated server; updating the software does not rewrite stored RDF.

## Expand real metadata relationships

A DCAT dataset is not inherently a tree. This browser uses declared membership:

- Catalog → `dcat:dataset` → dataset or dataset series.
- Dataset series → `dcat:seriesMember` → nested series or dataset.
- Dataset → `dcat:distribution` → source distribution.
- Dataset → ConstructDCAT `cx:hasAASSubmodel` → linked submodel resource.

Series are typed `dcat:DatasetSeries`. This demo requires the forward
`dcat:seriesMember` statements; inverse-only `dcat:inSeries` membership is not
normalized. DCAT 3 describes these concepts in its
[dataset series model](https://www.w3.org/TR/vocab-dcat-3/#dataset-series).
Grouping does not imply that dataset contents have been merged, assembled into
an AAS, or transferred. No hierarchy is inferred from an IRI, title, shared
asset type or `dct:relation`.

Expand the arrows to browse groups and load a dataset's distribution/submodel
links. Select a dataset's title to inspect it. Search retains the containing
catalog and group path for matching datasets. A group with multiple parents
appears on each declared path; cyclic paths stop expanding rather than loop.

## Interactive graph

The graph starts with the selected dataset, its immediate membership parent,
linked datasets, distributions and submodel resources. Literal titles,
keywords and descriptions appear in the resource inspector rather than as
nodes. Select **Show all resources** to include the catalog ancestor path,
vocabulary/type nodes and access URL resources in the returned description.

Drag a resource to arrange the graph, drag the background to pan, use the
zoom controls or scroll wheel, and select **Fit graph** to restore the view.
**Expand view** opens a larger graph workspace; Close or Escape returns it to
the detail panel. Keyboard users can Tab to resource nodes and press Enter or
Space to inspect them. Full IRIs appear in the inspector and node tooltips.

Selecting B's `a-frame` relation exposes **Explore dataset** for A's matching
listing. This opens A's description in A's graph. If multiple publishers use
that IRI, the inspector offers a separate action for each source. External
URLs are not fetched to build the graph. This is a dataset-neighborhood view,
not the entire Fuseki store, a reasoner, or a network crawler. Fuseki provides
RDF/query storage; the browser implements interaction without an external
JavaScript library or CDN.

## Run the partner presentation

1. Update the server from the repository root:

   ```bash
   git pull --ff-only
   docker compose up -d --build catalog
   ```

   The existing `.env`, tokens and persistent Fuseki data are retained. Confirm
   `/ready` returns 200, then reload the browser.

2. Publish A's updated `demo-data/participant-a/catalog-v1.ttl` using A's token.
   Publish B's [catalog-connector-demo.ttl](../demo-data/participant-b/catalog-connector-demo.ttl)
   using B's token. Choose these files in each standalone publisher, or run the
   existing simulator on the server with its existing `.env`:

   ```bash
   python3 scripts/edc_http_simulator.py \
     --catalog-url https://fedcat.tmdt.uni-wuppertal.de/catalog \
     --participant urn:demo:participant:a --env-file .env \
     --rdf demo-data/participant-a/catalog-v1.ttl
   python3 scripts/edc_http_simulator.py \
     --catalog-url https://fedcat.tmdt.uni-wuppertal.de/catalog \
     --participant urn:demo:participant:b --env-file .env \
     --rdf demo-data/participant-b/catalog-connector-demo.ttl
   ```

   Use the participant IDs actually configured on your server if they differ.
   Each POST replaces that participant's previous catalog, as before. Share
   only the individual participant's token with an independent publisher.

3. Expect **two catalogs and four datasets**. Open B → Building passports →
   Wall passports → Wall component passport. Inspect the requested DID,
   endpoint and `b-components` identifier. Expand the dataset to see its
   distribution and submodel link.
4. Search `did:web:participant-b` to find B's records; search `frame` to find A's
   frame export and B's related wall passport. Inspect the graph's `a-frame`
   resource and explore A's dataset. Run
   [publisher-links.rq](../demo-data/queries/publisher-links.rq) for a joined
   result across both source graphs.

The original flat B fixtures remain available. The nested sample has the same
two leaf datasets and explicit A links as `catalog-linked-to-a.ttl`; the series
organize them without adding datasets or changing ownership.
