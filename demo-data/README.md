# Original construction catalog fixtures

For a different story, see [one asset, three AAS submodel publishers](aas-dpp/README.md). That scenario is separate from the counts below.

These files provide deterministic DCAT/RDF snapshots for two simulated participants. The participant identity is selected by the simulator credential; it is not taken from the fixture.

## Snapshots

- `participant-a/catalog-v1.ttl` contains Frame export — revision 1 and Floor package.
- `participant-a/catalog-v2.ttl` updates the frame, removes Floor package and adds Envelope package.
- `participant-b/catalog-v1.ttl` contains Component passport set.
- `invalid/invalid-catalog.ttl` deliberately violates the catalog shape and demonstrates rejection without losing the last valid snapshot.

Participant A supplies IFC/BIM metadata and participant B supplies AAS metadata. Titles deliberately omit the word “wall”. Both use `cx:describesAssetType ifc:IfcWall`, so `queries/walls.rq` finds their semantic descriptions without inference or keyword matching.

On a fresh index, A v1 plus B v1 produces three datasets and two wall-query results. Replacing A v1 with A v2 keeps three datasets and produces three wall-query results. B remains unchanged.

## Query examples

- `queries/datasets.rq` lists graph, dataset and title.
- `queries/participants.rq` lists distinct participant graph IDs.
- `queries/walls.rq` finds BIM and AAS wall descriptions.
- `queries/ask.rq` checks whether the index contains any DCAT dataset.

The fixtures use [ConstructDCAT](https://github.com/jundahuang9123/ConstructDCAT) at commit `2effb755897b99342f8405afac96425f6c13649c`, version 0.1.0 (CC BY 4.0; Junda Huang), including the `https://w3id.org/construct-dcat#` terms `BIMDataset`, `AASDataset`, `describesAssetType`, `usesOntology` and `hasAASSubmodel`.

The `example.org` identifiers and download URLs are illustrative metadata. No referenced data-file content is transferred or stored by this demo.
