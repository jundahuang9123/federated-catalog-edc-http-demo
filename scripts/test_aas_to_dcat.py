"""Offline mapping checks: source identity, references, pagination and real links."""

import base64
import unittest
from urllib.parse import parse_qs, urlsplit

from rdflib import DCAT, DCTERMS, RDF, URIRef

from scripts.aas_to_dcat import CX, build_catalog, endpoint, identity, paginated

BASE = "https://aas.invalid"


class AasMappingTests(unittest.TestCase):
    def test_instance_and_unlinked_template_have_different_associations(self):
        shells = [
            {
                "id": "urn:shell:one",
                "assetInformation": {"globalAssetId": "urn:asset:one"},
                "submodels": [
                    {
                        "type": "ModelReference",
                        "keys": [{"type": "Submodel", "value": "urn:sm:one"}],
                    }
                ],
            }
        ]
        submodels = [
            {
                "id": "urn:sm:one",
                "idShort": "Tracking",
                "kind": "Instance",
                "submodelElements": [{"value": "DO-NOT-COPY"}],
            },
            {
                "id": "urn:sm:template",
                "idShort": "DPP",
                "kind": "Template",
                "semanticId": {
                    "type": "ExternalReference",
                    "keys": [{"type": "GlobalReference", "value": "urn:semantic:dpp"}],
                },
            },
        ]
        graph, report = build_catalog(
            BASE,
            shells,
            submodels,
            "urn:catalog",
            "urn:contact",
            "2026-09-23T00:00:00Z",
        )
        self.assertEqual(len(list(graph.subjects(RDF.type, DCAT.Catalog))), 1)
        self.assertEqual(len(list(graph.subjects(RDF.type, DCAT.Dataset))), 2)
        self.assertEqual(report["shell_linked_submodels"], 1)
        self.assertIn(
            (URIRef("urn:sm:one"), DCTERMS.isPartOf, URIRef("urn:shell:one")), graph
        )
        self.assertFalse(
            list(graph.objects(URIRef("urn:sm:template"), DCTERMS.isPartOf))
        )
        self.assertIn(
            (URIRef("urn:sm:template"), DCTERMS.type, URIRef("urn:semantic:dpp")), graph
        )
        self.assertNotIn("DO-NOT-COPY", graph.serialize(format="turtle"))
        self.assertFalse(list(graph.triples((None, DCTERMS.conformsTo, None))))
        for record in graph.subjects(RDF.type, DCAT.Dataset):
            submodel = str(graph.value(record, CX.hasAASSubmodel))
            distribution = graph.value(record, DCAT.distribution)
            self.assertEqual(
                str(graph.value(distribution, DCAT.accessURL)),
                endpoint(BASE, "submodels", submodel),
            )

    def test_pagination_follows_last_cursor_even_for_short_page(self):
        urls = []

        def fetch(url):
            urls.append(url)
            if len(urls) == 1:
                return {
                    "result": [{"id": "urn:shell"}],
                    "paging_metadata": {"cursor": "a+b/="},
                }
            return {"result": [], "paging_metadata": {}}

        self.assertEqual(paginated(BASE, "shells", fetch), [{"id": "urn:shell"}])
        self.assertEqual(parse_qs(urlsplit(urls[1]).query)["cursor"], ["a+b/="])

    def test_repeating_page_and_missing_reference_abort(self):
        def fetch(_url):
            return {
                "result": [{"id": "urn:one"}],
                "paging_metadata": {"cursor": "same"},
            }

        with self.assertRaises(ValueError):
            paginated(BASE, "shells", fetch)
        shell = {
            "id": "urn:shell",
            "submodels": [
                {
                    "type": "ModelReference",
                    "keys": [{"type": "Submodel", "value": "urn:missing"}],
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "missing submodel"):
            build_catalog(
                BASE, [shell], [], "urn:catalog", "urn:contact", "2026-09-23T00:00:00Z"
            )

    def test_access_url_encoding_is_reversible_and_identity_is_not_url(self):
        raw = "https://source.example/id/ä?x=1&y=2"
        url = endpoint(BASE, "submodels", raw)
        encoded = url.rsplit("/", 1)[1]
        self.assertEqual(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode(), raw
        )
        self.assertEqual(str(identity(raw, "submodel")), raw)
        self.assertEqual(
            str(identity("local asset 123", "asset")),
            "urn:aas:asset:local%20asset%20123",
        )


if __name__ == "__main__":
    unittest.main()
