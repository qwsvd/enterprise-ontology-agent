"""Offline MCP v2 tests for the read-only ontology tools."""

import inspect

import pytest
from mcp import Client

import enterprise_ontology_agent.mcp_server as mcp_server
from enterprise_ontology_agent.mcp_server import create_mcp_server
from enterprise_ontology_agent.ontology import ObjectType, OntologyObject


class FakeRetrieval:
    def __init__(self, results: list[OntologyObject] | None = None) -> None:
        self.results = results or []
        self.calls: list[tuple[str, str]] = []
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def owners_for_service(self, value: str) -> list[OntologyObject]:
        self.calls.append(("owners_for_service", value))
        return self.results

    def repositories_for_service(self, value: str) -> list[OntologyObject]:
        self.calls.append(("repositories_for_service", value))
        return self.results

    def services_affected_by_incident(self, value: str) -> list[OntologyObject]:
        self.calls.append(("services_affected_by_incident", value))
        return self.results

    def teams_for_person(self, value: str) -> list[OntologyObject]:
        self.calls.append(("teams_for_person", value))
        return self.results


def _object() -> OntologyObject:
    return OntologyObject(
        id="team-payments",
        name="Payments",
        object_type=ObjectType.TEAM,
        source_url="https://example.test/payments",
        source_type="test",
        external_id="external-payments",
    )


def test_mcp_server_has_no_llm_or_agent_dependency() -> None:
    source = inspect.getsource(mcp_server)

    assert "GraphAgent" not in source
    assert "OpenAICompatibleClient" not in source


@pytest.mark.anyio
async def test_server_exposes_exactly_four_read_only_tools() -> None:
    server = create_mcp_server(lambda: FakeRetrieval())

    async with Client(server) as client:
        tools = (await client.list_tools()).tools

    assert {tool.name for tool in tools} == {
        "owners_for_service",
        "repositories_for_service",
        "services_affected_by_incident",
        "teams_for_person",
    }
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.idempotent_hint is True
        assert tool.annotations.open_world_hint is False


@pytest.mark.anyio
async def test_tool_schemas_require_the_expected_single_argument() -> None:
    server = create_mcp_server(lambda: FakeRetrieval())

    async with Client(server) as client:
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert tools["owners_for_service"].input_schema["required"] == ["service_name"]
    assert tools["repositories_for_service"].input_schema["required"] == [
        "service_name"
    ]
    assert tools["services_affected_by_incident"].input_schema["required"] == [
        "incident_name"
    ]
    assert tools["teams_for_person"].input_schema["required"] == ["person_name"]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool_name", "argument_name", "argument_value"),
    [
        ("owners_for_service", "service_name", "Payment API"),
        ("repositories_for_service", "service_name", "Payment API"),
        ("services_affected_by_incident", "incident_name", "INC-204"),
        ("teams_for_person", "person_name", "Alice"),
    ],
)
async def test_tools_dispatch_only_to_the_matching_retrieval_method(
    tool_name: str,
    argument_name: str,
    argument_value: str,
) -> None:
    retrieval = FakeRetrieval([_object()])
    server = create_mcp_server(lambda: retrieval)

    async with Client(server) as client:
        await client.call_tool(tool_name, {argument_name: argument_value})

    assert retrieval.calls == [(tool_name, argument_value)]
    assert retrieval.closed is True


@pytest.mark.anyio
async def test_tool_output_is_structured_and_preserves_provenance() -> None:
    server = create_mcp_server(lambda: FakeRetrieval([_object()]))

    async with Client(server) as client:
        result = await client.call_tool(
            "owners_for_service", {"service_name": "Payment API"}
        )

    assert result.structured_content == {
        "result": [
            {
                "id": "team-payments",
                "name": "Payments",
                "object_type": "Team",
                "source_url": "https://example.test/payments",
                "source_type": "test",
                "external_id": "external-payments",
            }
        ]
    }


@pytest.mark.anyio
async def test_empty_graph_result_is_a_structured_empty_list() -> None:
    server = create_mcp_server(lambda: FakeRetrieval())

    async with Client(server) as client:
        result = await client.call_tool(
            "owners_for_service", {"service_name": "Unknown API"}
        )

    assert result.structured_content == {"result": []}


@pytest.mark.anyio
async def test_blank_input_fails_without_querying_the_graph() -> None:
    retrieval = FakeRetrieval()
    server = create_mcp_server(lambda: retrieval)

    async with Client(server) as client:
        result = await client.call_tool("owners_for_service", {"service_name": "   "})

    assert result.is_error is True
    assert "service_name must not be blank" in result.content[0].text
    assert retrieval.calls == []
