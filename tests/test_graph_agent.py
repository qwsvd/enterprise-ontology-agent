"""Tests for the bounded tool-calling graph agent."""

import json

import pytest

from enterprise_ontology_agent.infrastructure import GraphAgent
from enterprise_ontology_agent.ontology import ObjectType, OntologyObject


class FakeLLMClient:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.calls = []

    def chat_with_tools(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
    ) -> dict[str, object]:
        self.calls.append((messages, tools))
        return self.responses.pop(0)


class FakeRetrieval:
    def __init__(self, results: list[OntologyObject] | None = None) -> None:
        self.results = results or []
        self.calls = []

    def owners_for_service(self, name: str) -> list[OntologyObject]:
        self.calls.append(("owners_for_service", name))
        return self.results

    def repositories_for_service(self, name: str) -> list[OntologyObject]:
        self.calls.append(("repositories_for_service", name))
        return self.results

    def services_affected_by_incident(self, name: str) -> list[OntologyObject]:
        self.calls.append(("services_affected_by_incident", name))
        return self.results

    def teams_for_person(self, name: str) -> list[OntologyObject]:
        self.calls.append(("teams_for_person", name))
        return self.results


def _tool_call(name: str, arguments: dict[str, str]) -> dict[str, object]:
    return {
        "tool_calls": [
            {
                "id": "call-1",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ]
    }


def _object() -> OntologyObject:
    return OntologyObject(
        id="team-payments",
        name="Payments",
        object_type=ObjectType.TEAM,
        source_url="https://example.test/teams/payments",
        source_type="example",
        external_id="team-1",
    )


def test_agent_rejects_a_direct_answer_before_a_graph_tool_call() -> None:
    client = FakeLLMClient([{"content": "Payments owns Payment API."}])

    with pytest.raises(ValueError, match="Agent must use a graph tool before answering"):
        GraphAgent(client, FakeRetrieval()).answer("Who owns Payment API?")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("tool_name", "argument_name", "argument_value", "answer"),
    [
        ("owners_for_service", "service_name", "Payment API", "Payments owns it."),
        (
            "repositories_for_service",
            "service_name",
            "Payment API",
            "payment-service implements it.",
        ),
        (
            "services_affected_by_incident",
            "incident_name",
            "INC-204",
            "Payment API was affected.",
        ),
        ("teams_for_person", "person_name", "Alice", "Alice is in Payments."),
    ],
)
def test_agent_dispatches_each_typed_retrieval_tool(
    tool_name: str,
    argument_name: str,
    argument_value: str,
    answer: str,
) -> None:
    client = FakeLLMClient([_tool_call(tool_name, {argument_name: argument_value}), {"content": answer}])
    retrieval = FakeRetrieval([_object()])

    assert GraphAgent(client, retrieval).answer("question") == answer  # type: ignore[arg-type]
    assert retrieval.calls == [(tool_name, argument_value)]


def test_agent_sends_compact_tool_results_back_to_llm() -> None:
    client = FakeLLMClient(
        [
            _tool_call("owners_for_service", {"service_name": "Payment API"}),
            {"content": "Payments owns Payment API."},
        ]
    )
    retrieval = FakeRetrieval([_object()])

    GraphAgent(client, retrieval).answer("Who owns Payment API?")  # type: ignore[arg-type]

    tool_message = client.calls[1][0][-1]
    assert tool_message["role"] == "tool"
    assert json.loads(tool_message["content"]) == [_object().model_dump(mode="json")]


def test_agent_returns_empty_graph_result_to_llm() -> None:
    client = FakeLLMClient(
        [
            _tool_call("owners_for_service", {"service_name": "Unknown"}),
            {"content": "The graph contains no matching result."},
        ]
    )
    retrieval = FakeRetrieval()

    assert GraphAgent(client, retrieval).answer("Who owns Unknown?") == (
        "The graph contains no matching result."
    )  # type: ignore[arg-type]
    assert client.calls[1][0][-1]["content"] == "[]"


@pytest.mark.parametrize(
    "tool_call",
    [
        _tool_call("owners_for_service", {"service_name": "   "}),
        {
            "tool_calls": [
                {"id": "call-1", "type": "function", "function": {"name": "owners_for_service", "arguments": "not json"}}
            ]
        },
    ],
)
def test_agent_rejects_malformed_tool_arguments(tool_call: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="argument"):
        GraphAgent(FakeLLMClient([tool_call]), FakeRetrieval()).answer("question")  # type: ignore[arg-type]


def test_agent_rejects_unknown_tool_name() -> None:
    client = FakeLLMClient([_tool_call("run_cypher", {"query": "MATCH (n)"})])

    with pytest.raises(ValueError, match="Unknown graph tool"):
        GraphAgent(client, FakeRetrieval()).answer("question")  # type: ignore[arg-type]


def test_agent_rejects_more_than_three_tool_iterations() -> None:
    responses = [_tool_call("owners_for_service", {"service_name": "Payment API"}) for _ in range(4)]

    with pytest.raises(ValueError, match="Exceeded maximum"):
        GraphAgent(FakeLLMClient(responses), FakeRetrieval()).answer("question")  # type: ignore[arg-type]
