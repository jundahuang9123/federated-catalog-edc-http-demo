from abc import ABC, abstractmethod

from fastapi import APIRouter


class IngestSource(ABC):
    """Catalog push entrypoint.

    Expected push contract:
    POST /catalog with an RDF request body, a supported RDF content type, and a
    bearer token mapped to one configured participant.

    Successful pushes return 200. Authentication or SHACL rejection returns a
    readable 4xx response with errors.
    """

    @abstractmethod
    def routes(self) -> APIRouter:
        raise NotImplementedError
