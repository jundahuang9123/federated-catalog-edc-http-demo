"""DCAT/RDF ingestion for the simulated EDC HTTP delivery boundary."""

from __future__ import annotations

import logging
import os
from uuid import uuid4

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from core.interfaces.ingest import IngestSource
from core.interfaces.store import CatalogStore
from core.interfaces.validation import ValidationGate
from core.shared.participant_graph import graph_uri_for_participant
from core.shared.rdf import (
    CONTENT_TYPE_TO_RDFLIB_FORMAT,
    normalize_content_type,
    serialize_rdf_to_turtle,
)
from core.shared.sparql import sparql_routes
from modes.http_demo.auth import HttpDemoAuthError, HttpDemoTokenAuth

logger = logging.getLogger(__name__)


def _error_response(
    *,
    status_code: int,
    error: str,
    detail: str,
    stage: str,
    request_id: str,
    errors: list[str] | None = None,
) -> JSONResponse:
    payload: dict[str, object] = {
        "error": error,
        "detail": detail,
        "stage": stage,
        "request_id": request_id,
    }
    if errors is not None:
        payload["errors"] = errors
    return JSONResponse(status_code=status_code, content=payload)


class HttpDemoIngest(IngestSource):
    def __init__(
        self,
        validation: ValidationGate,
        store: CatalogStore,
        auth: HttpDemoTokenAuth,
    ) -> None:
        self.validation = validation
        self.store = store
        self.auth = auth
        self.max_request_bytes = int(os.getenv("CATALOG_MAX_INGEST_BYTES", "2097152"))

    def routes(self) -> APIRouter:
        router = APIRouter()
        router.include_router(sparql_routes(self.store))

        @router.post("/catalog", response_model=None)
        async def push_catalog(
            request: Request,
            declared_participant_id: str | None = Header(default=None, alias="X-Participant-Id"),
            request_id_header: str | None = Header(default=None, alias="X-Request-Id"),
        ):
            request_id = (request_id_header or "").strip()[:128] or str(uuid4())
            try:
                participant = self.auth.authenticate(request)
            except HttpDemoAuthError as exc:
                logger.info(
                    "HTTP demo push rejected at auth stage",
                    extra={"request_id": request_id, "stage": "auth", "error": exc.error},
                )
                return _error_response(
                    status_code=exc.status_code,
                    error=exc.error,
                    detail=exc.detail,
                    stage="auth",
                    request_id=request_id,
                )

            participant_id = participant.participant_id
            if declared_participant_id and declared_participant_id.strip() != participant_id:
                return _error_response(
                    status_code=403,
                    error="participant_mismatch",
                    detail="Participant identity is derived from the bearer token",
                    stage="auth",
                    request_id=request_id,
                )

            content_type_header = request.headers.get("content-type")
            content_type = normalize_content_type(content_type_header)
            if not content_type_header or content_type not in CONTENT_TYPE_TO_RDFLIB_FORMAT:
                return _error_response(
                    status_code=415,
                    error="unsupported_media_type",
                    detail="Send RDF with a supported Content-Type such as text/turtle",
                    stage="parse",
                    request_id=request_id,
                )

            raw_body = bytearray()
            async for chunk in request.stream():
                raw_body.extend(chunk)
                if len(raw_body) > self.max_request_bytes:
                    return _error_response(
                        status_code=413,
                        error="payload_too_large",
                        detail=f"RDF payload exceeds {self.max_request_bytes} bytes",
                        stage="parse",
                        request_id=request_id,
                    )
            try:
                rdf_payload = raw_body.decode("utf-8")
            except UnicodeDecodeError:
                return _error_response(
                    status_code=422,
                    error="invalid_rdf_encoding",
                    detail="RDF payload must be UTF-8 encoded",
                    stage="validation",
                    request_id=request_id,
                )

            rdf_format = CONTENT_TYPE_TO_RDFLIB_FORMAT[content_type]
            validation = self.validation.validate(rdf_payload, format=rdf_format)
            if not validation.ok:
                logger.info(
                    "HTTP demo push rejected by SHACL validation",
                    extra={
                        "request_id": request_id,
                        "stage": "validation",
                        "participant_id": participant_id,
                    },
                )
                return _error_response(
                    status_code=422,
                    error="validation_failed",
                    detail="RDF payload failed parsing or SHACL validation",
                    stage="validation",
                    request_id=request_id,
                    errors=validation.errors,
                )

            try:
                normalized_turtle = serialize_rdf_to_turtle(rdf_payload, format=rdf_format)
                graph_id = graph_uri_for_participant(participant_id)
                self.store.replace_graph(graph_id, normalized_turtle)
            except Exception:
                logger.exception(
                    "HTTP demo push failed at store stage",
                    extra={
                        "request_id": request_id,
                        "stage": "store",
                        "participant_id": participant_id,
                    },
                )
                return _error_response(
                    status_code=502,
                    error="store_write_failed",
                    detail="Catalog store write failed",
                    stage="store",
                    request_id=request_id,
                )

            logger.info(
                "HTTP demo push accepted and stored",
                extra={
                    "request_id": request_id,
                    "stage": "store",
                    "participant_id": participant_id,
                    "graph": graph_id,
                },
            )
            return {
                "accepted": True,
                "mode": "http-demo",
                "interface": "edc-http-adapter-simulator",
                "participant_id": participant_id,
                "graph": graph_id,
                "request_id": request_id,
            }

        return router
