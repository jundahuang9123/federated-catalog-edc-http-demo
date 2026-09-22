# Group AAS API: linked catalog metadata

This catalog is generated from the group's [BaSyx API](http://132.195.160.222:8081/swagger-ui/index.html). It contains **metadata linked to real API records**, not a copy of their submodel-element values. The API itself may host demonstration data; reachability does not establish its business authenticity or DPP conformity.

## What was found

The [capture report](catalog.report.json) records the inspection timestamp and link checks. This committed snapshot contains:

| Source records | Catalog treatment |
| --- | --- |
| 8 AAS shells, each with a different GS1 global asset identifier | Retain the exact shell–submodel–asset relationships returned by the service |
| 8 `TrackingAndTracing` instances | One discoverable dataset per submodel, linked to its actual asset and shell |
| 5 unlinked templates | Separate discoverable entries; no invented asset or shell association |
| `DPP-EU` template | Preserve its source-declared semantic ID as a type reference; no conformity claim |

The five templates are `TrackingAndTracing`, `HerstellerInformationen`, `Logistik`, `DPP-EU` and `SustainabilityData`. The first is a template separate from the eight similarly named instances.

**These records describe eight different assets.** They must not all be grouped as submodels of one asset. The service did not expose shell references to the five templates in this capture. The synthetic [three-publisher shared-asset scenario](../aas-dpp/README.md) remains a separate demonstration until actual associations are established.

## Use the catalog

1. Open [catalog.ttl](catalog.ttl). It is one complete publisher catalog with 13 dataset entries.
2. Replace the explicitly pending `dcat:contactPoint` IRI (`urn:tmdt:aas-demo:contact-pending`) with the group's real contact IRI, or regenerate with `--contact`. No operator contact was supplied; the placeholder is not a working contact address.
3. Start the [publisher](../../publisher/README.md), use a token reserved for this source, and publish this file to your deployed catalog. Using a token already used for another fixture replaces that token's previous catalog.
4. Search for `DPP-EU`, `SustainabilityData`, `TrackingAndTracing`, or an asset identifier. Select a result and use **Open source data** to reach the original submodel JSON.
5. Run [submodels.rq](submodels.rq) to see submodel IDs, optional asset/shell references, the declared semantic type and the real access URL.

The captured 13 submodel endpoints and 8 shell endpoints were checked using HTTP GET and matching returned `id` values. These are point-in-time checks, not availability guarantees. Source endpoints use the HTTP address provided by the user. Publishing metadata uses the separately configured catalog URL, normally HTTPS.

## Regenerate from the API

From the repository root, after installing the catalog dependencies as described in the root README:

```bash
.venv/bin/python scripts/aas_to_dcat.py \
  --api-base http://132.195.160.222:8081 \
  --catalog-id urn:tmdt:aas-demo:catalog \
  --contact '<actual-contact-IRI-or-mailto-address>' \
  --output demo-data/group-aas/catalog.ttl \
  --verify-links
```

This performs read-only requests, follows pagination, validates the generated RDF and writes the catalog plus a capture report. It does **not** publish the catalog or change the AAS service. Regeneration is manual. An HTTP failure, unsupported identity reference or missing referenced submodel aborts the export before replacing the previous catalog file.

Only selected discovery fields become RDF. Even when verification reads a full submodel response, its operational values are neither copied into the output nor logged. The API does not offer a transactional snapshot across these separate requests, so avoid changing source identifiers during an export.

## Identifier and vocabulary mapping

| API field | RDF mapping |
| --- | --- |
| Submodel `id` | Preserved as the `cx:hasAASSubmodel` target and `dct:identifier` |
| `idShort`, kind and asset identifier | Searchable title/keywords; templates explicitly distinguished from instances |
| Submodel description/display name | `dct:description` / `dct:alternative` |
| Shell's `submodels` references | `dct:isPartOf` on the corresponding submodel anchor, an explicit demo mapping |
| Shell's `assetInformation.globalAssetId` | `dct:subject` shared by its dataset, submodel and shell |
| A single-key external `semanticId` | `dct:type` on dataset and submodel, an explicit demo mapping of the source assertion |
| API base + base64url-encoded `id` | Actual `dcat:accessURL` to the submodel JSON |

Some **actual API identifiers contain `example.com`**. They are preserved verbatim; their HTTP appearance does not mean they are working access URLs. The working data links use `132.195.160.222:8081/submodels/...`. Non-IRI identifiers are encoded into a deterministic `urn:aas:...` IRI while their exact original string is retained in `dct:identifier`.

The `urn:catalog-record:aas-submodel:...` dataset identifiers and `urn:tmdt:aas-demo:catalog` catalog identifier are minted discovery records, not new source objects. Source descriptions and semantic IDs are retained as assertions from the API; nothing here creates a new ConstructDCAT term or validates an official DPP template.
