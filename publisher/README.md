# EDC dummy publisher — individual setup

A minimal browser publisher for **individual testing and demonstrations**. Each participant runs their own instance on their laptop or workstation and sends DCAT metadata to the shared catalog.

This is an HTTP sender dummy, not an Eclipse EDC connector. It does not implement DSP, contract negotiation, policy enforcement, or EDC control/data planes. No Solid login or Pod is needed.

## Start

From the repository root, with Python 3.11 or newer:

```bash
python3 publisher/server.py
```

No Python packages need installing. Open **http://127.0.0.1:8787**. Stop with Ctrl+C.

Alternatively, with Docker Compose:

```bash
docker compose -f publisher/compose.yaml up --build
```

Both options run only the publisher, independently of the central catalog. The `publisher/` folder is self-contained and can be copied to another machine. The repository is private, so installation from GitHub requires repository access or a copy supplied by the operator. Docker requires installation and image downloads; Python requires a compatible interpreter. One-command startup assumes the source and one of these runtimes are already present.

## Publish

1. Obtain the deployed catalog URL and **your own participant token** from the operator.
2. Enter the URL and token in the local page.
3. Select a UTF-8 DCAT file, optionally inspect its text preview, and click **Publish to catalog**.
4. Read the catalog response, then refresh the central catalog UI.

Use `https://your-catalog-domain` or its `/catalog` endpoint. Remote destinations require HTTPS. For a catalog running directly on the same machine, the Python sender also supports `http://127.0.0.1:8000/catalog`. Inside Docker, localhost refers to the publisher container; use the deployed HTTPS catalog for the Docker sender.

Supported inputs: `.ttl`, `.jsonld`, `.json`, `.rdf`, `.nt`, up to 2 MB. JSON-LD must use embedded contexts, as required by the catalog. The preview is text only; the catalog performs RDF parsing and SHACL validation.

The existing `demo-data/` folder contains A v1, A v2, B v1 and an invalid fixture. The token determines ownership; the file name does not. Publish with separate tokens to demonstrate separate participants.

## Data flow

```text
Your browser (localhost)
  -> local Python sender
  -> HTTPS POST /catalog with your token and RDF
  -> central authentication + SHACL validation
  -> replace your participant graph in Fuseki
  -> discovery UI / SPARQL
```

Each publisher has exactly one catalog. A file must contain exactly one `dcat:Catalog` with an IRI and link every included dataset to it. A successful push replaces the participant's complete snapshot, even if the catalog IRI changes. A valid catalog with no datasets clears your old dataset listings. It is not an append or file-transfer operation. The referenced datasets themselves are not uploaded. HTTP 401 indicates invalid credentials; 422 indicates rejected RDF; 502 indicates a storage failure. A network error can occur after the catalog accepted a request, so check the catalog before concluding that nothing changed.

## Individual use boundary

- The UI is bound to host loopback. No publisher domain or inbound internet port is required.
- The local service sends the remote request, so the catalog needs no browser CORS changes.
- Each participant receives only their own token, never the server's full participant mapping or Fuseki password.
- Tokens and RDF remain in process/page memory; no local file or browser storage is used. Closing/reloading the page clears the inputs. The accepted metadata persists at the catalog and is publicly readable there.
- Redirects are rejected to avoid forwarding a token to a different destination. Use the final catalog URL.
- This is not a hosted multi-user service. Keep its port private. To run on a remote workstation, use an SSH tunnel to its loopback port.
- Anyone with the source/runtime can start a dummy. Only operator-configured participants can publish. There is no self-registration.

## Test

From the repository root:

```bash
python3 -m unittest discover -s publisher -p 'test_*.py' -v
```
