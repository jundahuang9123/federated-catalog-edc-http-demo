# One asset, three publishers

**Synthetic, runnable catalog metadata.** These fixtures are not the group's original AAS/DPP data. They contain no AAS JSON payloads and their `example.org` access URLs are placeholders. They demonstrate discovery, not payload retrieval or DPP compliance.

| Publisher | Snapshot | Contribution |
| --- | --- | --- |
| Manufacturer | [manufacturer-v1.ttl](manufacturer-v1.ttl) | Identity and technical information |
| Environmental-data provider | [environment-v1.ttl](environment-v1.ttl) | Material and environmental information |
| Operator | [operator-v1.ttl](operator-v1.ttl) | Maintenance information |
| Operator, replacement | [operator-v2.ttl](operator-v2.ttl) | Updated maintenance metadata |

Each snapshot contains one catalog, one AAS dataset and one submodel discovery anchor. They share an asset IRI and a shell IRI, while all catalog, dataset and submodel IRIs remain distinct. Each source keeps its own named graph.

## Run

1. The operator configures three distinct participant tokens. Use separate participant identities for this scenario if the original BIM/AAS fixtures should remain published. Adding participants requires recreating the catalog with the updated environment; see [deployment](../../docs/DEPLOYMENT.md#token-rotation-and-participant-changes).
2. Start the [individual publisher](../../publisher/README.md) on each machine. Enter the common catalog URL and that publisher's own token.
3. Publish the manufacturer, environment and operator v1 files with the three respective tokens.
4. Search for **Pump 001**. With only these fixtures present, three datasets from three catalogs appear.
5. Run [asset-submodels.rq](asset-submodels.rq) in the SPARQL editor. Expect three source-labelled submodel references for the same asset and shell. The graph column identifies each authenticated publisher; RDF labels do not establish ownership.
6. Publish operator v2 with the **same operator token**. The query still returns three rows; only the operator title changes. The other two graphs are unchanged.

Using one token for all three files would replace the same publisher's catalog three times, leaving only the final file. No new publisher software is needed to add another source—just another configured token and complete catalog snapshot.

## Meaning of the links

`cx:AASDataset` and `cx:hasAASSubmodel` come from ConstructDCAT 0.1.0. The use of `dct:subject` for asset identity and `dct:isPartOf` for shell membership is an explicit convention of this demo, not a new ConstructDCAT or official AAS mapping. No new vocabulary term or official submodel template ID is invented here.

For real data, verify asset ID, shell ID, submodel ID and template semantic ID independently. An asset type such as “pump” is not an individual asset identifier. See [the mapping and real-data plan](../../docs/AAS_DPP_SCENARIO.md).
