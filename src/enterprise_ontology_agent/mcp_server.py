"""Read-only MCP v2 tools for the enterprise ontology graph."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Protocol

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from enterprise_ontology_agent.infrastructure.graph_retrieval import (
    Neo4jGraphRetrieval,
)
from enterprise_ontology_agent.ontology import ObjectType, OntologyObject


class GraphRetrieval(Protocol):
    """The read-only graph operations exposed through MCP."""

    def close(self) -> None:
        """Release the graph connection."""

    def owners_for_service(self, service_name: str) -> list[OntologyObject]:
        """Return owners for a service."""

    def repositories_for_service(self, service_name: str) -> list[OntologyObject]:
        """Return repositories for a service."""

    def services_affected_by_incident(self, incident_name: str) -> list[OntologyObject]:
        """Return services affected by an incident."""

    def teams_for_person(self, person_name: str) -> list[OntologyObject]:
        """Return teams for a person."""


class GraphObjectResult(BaseModel):
    """A machine-readable ontology object returned by an MCP graph tool."""

    id: str
    name: str
    object_type: ObjectType
    source_url: str | None = None
    source_type: str | None = None
    external_id: str | None = None


@dataclass
class ServerContext:
    """Shared server-lifetime infrastructure used by MCP tool handlers."""

    retrieval: GraphRetrieval


_READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    idempotentHint=True,
    openWorldHint=False,
)


def create_mcp_server(
    retrieval_factory: Callable[[], GraphRetrieval] = Neo4jGraphRetrieval.from_environment,
) -> MCPServer[ServerContext]:
    """Build an MCP v2 server with one shared Neo4j retrieval instance."""

    @asynccontextmanager
    async def lifespan(_server: MCPServer[ServerContext]) -> AsyncIterator[ServerContext]:
        retrieval = retrieval_factory()
        try:
            yield ServerContext(retrieval=retrieval)
        finally:
            retrieval.close()

    server = MCPServer("Enterprise Ontology Agent", lifespan=lifespan)

    @server.tool(annotations=_READ_ONLY_ANNOTATIONS)
    def owners_for_service(
        service_name: str,
        ctx: Context[ServerContext],
    ) -> list[GraphObjectResult]:
        """Find Teams that own a Service."""
        _require_nonblank(service_name, "service_name")
        return _results(
            ctx.request_context.lifespan_context.retrieval.owners_for_service(
                service_name
            )
        )

    @server.tool(annotations=_READ_ONLY_ANNOTATIONS)
    def repositories_for_service(
        service_name: str,
        ctx: Context[ServerContext],
    ) -> list[GraphObjectResult]:
        """Find Repositories that implement a Service."""
        _require_nonblank(service_name, "service_name")
        return _results(
            ctx.request_context.lifespan_context.retrieval.repositories_for_service(
                service_name
            )
        )

    @server.tool(annotations=_READ_ONLY_ANNOTATIONS)
    def services_affected_by_incident(
        incident_name: str,
        ctx: Context[ServerContext],
    ) -> list[GraphObjectResult]:
        """Find Services affected by an Incident."""
        _require_nonblank(incident_name, "incident_name")
        return _results(
            ctx.request_context.lifespan_context.retrieval.services_affected_by_incident(
                incident_name
            )
        )

    @server.tool(annotations=_READ_ONLY_ANNOTATIONS)
    def teams_for_person(
        person_name: str,
        ctx: Context[ServerContext],
    ) -> list[GraphObjectResult]:
        """Find Teams that a Person belongs to."""
        _require_nonblank(person_name, "person_name")
        return _results(
            ctx.request_context.lifespan_context.retrieval.teams_for_person(person_name)
        )

    return server


def _require_nonblank(value: str, field_name: str) -> None:
    if not value.strip():
        raise ToolError(f"{field_name} must not be blank")


def _results(objects: list[OntologyObject]) -> list[GraphObjectResult]:
    return [
        GraphObjectResult(
            id=ontology_object.id,
            name=ontology_object.name,
            object_type=ontology_object.object_type,
            source_url=ontology_object.source_url,
            source_type=ontology_object.source_type,
            external_id=ontology_object.external_id,
        )
        for ontology_object in objects
    ]


mcp = create_mcp_server()
