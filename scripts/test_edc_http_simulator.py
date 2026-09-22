import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts.edc_http_simulator import main, publish_catalog, validate_catalog_url


class _Response:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode()


class SimulatorTests(unittest.TestCase):
    def test_publish_sends_expected_boundary_without_participant_header(self):
        seen = {}

        def opener(request, timeout):
            seen["request"] = request
            seen["timeout"] = timeout
            return _Response(
                {
                    "accepted": True,
                    "participant_id": "urn:demo:participant:a",
                    "graph": "urn:catalog:a",
                }
            )

        with tempfile.TemporaryDirectory() as directory:
            rdf_path = Path(directory) / "catalog.ttl"
            rdf_path.write_text("<urn:s> <urn:p> <urn:o> .")
            status, payload = publish_catalog(
                catalog_url="https://catalog.example/catalog",
                rdf_path=rdf_path,
                token="secret-token",
                request_id="test-request",
                timeout=7,
                opener=opener,
            )

        request = seen["request"]
        self.assertEqual(status, 200)
        self.assertTrue(payload["accepted"])
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.full_url, "https://catalog.example/catalog")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(request.get_header("Content-type"), "text/turtle")
        self.assertEqual(request.get_header("X-participant-id"), None)
        self.assertEqual(request.get_header("X-request-id"), "test-request")
        self.assertEqual(seen["timeout"], 7)

    def test_remote_plain_http_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate_catalog_url("http://catalog.example/catalog")

    def test_local_plain_http_is_allowed(self):
        self.assertEqual(
            validate_catalog_url("http://127.0.0.1:8000/catalog"),
            "http://127.0.0.1:8000/catalog",
        )

    def test_trailing_slash_is_normalized(self):
        self.assertEqual(
            validate_catalog_url("https://catalog.example/catalog/"),
            "https://catalog.example/catalog",
        )

    def test_catalog_endpoint_path_is_required(self):
        with self.assertRaisesRegex(ValueError, "/catalog"):
            validate_catalog_url("https://catalog.example/datasets")

    def test_url_credentials_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute endpoint"):
            validate_catalog_url("https://user:secret@catalog.example/catalog")

    def test_invalid_port_is_a_configuration_error(self):
        with self.assertRaisesRegex(ValueError, "invalid"):
            validate_catalog_url("https://catalog.example:bad/catalog")

    def test_main_disclaims_scope_without_printing_token(self):
        token = "top-secret-demo-token"
        stdout = StringIO()
        stderr = StringIO()
        with tempfile.TemporaryDirectory() as directory:
            rdf_path = Path(directory) / "catalog.ttl"
            rdf_path.write_text("<urn:s> <urn:p> <urn:o> .")
            with (
                patch.dict(os.environ, {"EDC_SIMULATOR_TOKEN": token}),
                patch(
                    "scripts.edc_http_simulator.publish_catalog",
                    return_value=(
                        200,
                        {
                            "accepted": True,
                            "participant_id": "urn:demo:a",
                            "graph": "urn:catalog:a",
                            "request_id": "test-request",
                        },
                    ),
                ) as publish,
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                result = main(
                    [
                        "--catalog-url",
                        "https://catalog.example/catalog",
                        "--rdf",
                        str(rdf_path),
                    ]
                )

        output = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(result, 0)
        self.assertNotIn(token, output)
        self.assertIn("Simulation only", output)
        self.assertEqual(publish.call_args.kwargs["token"], token)


if __name__ == "__main__":
    unittest.main()
