# AAS/DPP demonstration: discover the parts of one asset

[Documentation index](README.md) · [Visual workflow](workflow.html) · [Runnable synthetic fixtures](../demo-data/aas-dpp/README.md)

## Demonstration claim

Several independent publishers contribute submodel descriptions for the same asset. The federated catalog discovers them together and returns their source catalogs and distribution links. It does not assemble an AAS, download the submodels, reconcile conflicting claims, or certify a complete DPP.

The initial synthetic asset is a building pump. Its choice can change once the group's earlier demonstration data is available.

| Source | Aspect of the shared asset | Responsibility |
| --- | --- | --- |
| Manufacturer | Identity and technical information | Publish its catalog and maintain its submodel |
| Environmental-data provider | Material and environmental information | Publish its own catalog and maintain its submodel |
| Operator | Maintenance and operation | Publish its own catalog and maintain its submodel |

The three contributions are illustrative aspects, not a prescribed set of submodels that makes a DPP complete. AAS separates asset identification from shell identity and independently identified submodels. The IDTA DPP discussion explains how multiple submodels can contribute to a passport, while an AAS alone is not automatically a complete DPP. [IDTA AAS/DPP guidance](https://industrialdigitaltwin.io/aas-specifications/IDTA-01001/v3.2/annex/dpp.html).

## Cover it with ConstructDCAT first

The existing [ConstructDCAT 0.1.0 vocabulary](https://github.com/jundahuang9123/ConstructDCAT/blob/2effb755897b99342f8405afac96425f6c13649c/construct-dcat.ttl) already provides `cx:AASDataset` and `cx:hasAASSubmodel`. Its submodel link deliberately has no formal RDF range. This first mapping uses those published terms and adds no vocabulary terms.

| Source information | Catalog representation | Status |
| --- | --- | --- |
| Publisher's complete listing | One `dcat:Catalog` with `dcat:dataset` links | Existing ingestion model |
| Submodel data offering | `dcat:Dataset` and `cx:AASDataset` | Existing ConstructDCAT class |
| Submodel ID or descriptor IRI | `cx:hasAASSubmodel` discovery anchor | Existing ConstructDCAT property |
| Physical asset identity | `dct:subject` with the agreed asset IRI | Demo convention; verify against the real global asset identifier |
| Shell identity | `dct:isPartOf` on the submodel anchor | Demo convention; verify the shell actually references the submodel |
| Dataset title, description, keywords | `dct:title`, `dct:description`, `dcat:keyword` | Searchable metadata |
| Data location and format | `dcat:Distribution`, `dcat:accessURL`, `dcat:mediaType` | Placeholder URLs in synthetic fixtures |
| Submodel template / semantic ID | Preserve and assess from the real export | Not fabricated or asserted in these fixtures |

The shared asset IRI is the discovery key. Similar names, shared classes and the same template semantic ID do not establish that records describe the same individual asset. Shell IDs, asset IDs and submodel IDs must not be used interchangeably. If the original IDs are not usable as RDF IRIs, document an explicit reversible mapping rather than changing them silently.

The query in this repository reads the stated links; it does not prove those links are true. Any downstream AAS application would retrieve the submodels, check their schemas and references, and decide whether they form a suitable shell view.

## Bring in the group's original data

1. Locate the prior AASX/JSON exports or repository and identify the asset the group demonstrated. Confirm which portions may be used as public demo metadata.
2. Inventory the actual shell ID, global asset identifier, referenced submodel IDs, versions, template semantic IDs and available distribution locations.
3. Create one ConstructDCAT catalog for that source, preserving its identifiers and exposing its actual submodel references. Keep source payloads separate from discovery metadata.
4. Validate the RDF with the catalog's existing gate. A separate AAS validation step is needed for the original JSON/AASX; catalog SHACL checks do not validate it.
5. Replace the corresponding synthetic contribution only after checking the mapping. Label remaining sources as synthetic. If they describe the same asset, make their synthetic association to the real asset explicit.
6. Add further dummy publishers incrementally, each with its own token and catalog. Demonstrate discovery, independent updates and a negative case where another asset's submodel is excluded.

The group's original export has not yet been inspected. This document is a mapping plan; the synthetic fixtures are executable examples, not a conversion of that export. No changes have been made to the separate ConstructDCAT vocabulary repository.
