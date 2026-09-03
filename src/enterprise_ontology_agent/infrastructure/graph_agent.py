"""A small tool-calling agent for typed Neo4j graph retrieval."""

import json
from collections.abc import Mapping
from typing import Any, Protocol

from enterprise_ontology_agent.infrastructure.graph_retrieval import (
    Neo4jGraphRetrieval,
)
from enterprise_ontology_agent.ontology import OntologyObject


MAX_TOOL_ITERATIONS = 3


class ToolCallingLLMClient(Protocol):
    """Minimal interface for the LLM tool-call loop."""

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return one OpenAI-compatible assistant message."""


class GraphAgent:
    """Answer a question using only four typed graph retrieval tools."""

    def __init__(
        self,
        client: ToolCallingLLMClient,
        retrieval: Neo4jGraphRetrieval,
    ) -> None:
        self._client = client
        self._retrieval = retrieval

    def answer(self, question: str) -> str:
        """Run the bounded tool-call loop and return the LLM's final answer."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": _AGENT_INSTRUCTIONS},
            {"role": "user", "content": question},
        ]
        tool_iterations = 0
        graph_tool_executed = False

        while True:
            message = self._client.chat_with_tools(messages, _GRAPH_TOOLS)
            tool_calls = message.get("tool_calls")
            if not tool_calls:
                if not graph_tool_executed:
                    raise ValueError("Agent must use a graph tool before answering.")
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("LLM did not return a final answer")
                return content
            if not isinstance(tool_calls, list):
                raise ValueError("LLM tool_calls must be a list")

            tool_iterations += 1
            if tool_iterations > MAX_TOOL_ITERATIONS:
                raise ValueError(
                    f"Exceeded maximum of {MAX_TOOL_ITERATIONS} LLM/tool iterations"
                )

            messages.append(
                {
                    "role": "assistant",
                    "content": message.get("content"),
                    "tool_calls": tool_calls,
                }
            )
            for tool_call in tool_calls:
                call_id, name, argument = _validate_tool_call(tool_call)
                results = _run_retrieval_tool(self._retrieval, name, argument)
                graph_tool_executed = True
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(
                            [result.model_dump(mode="json") for result in results]
                        ),
                    }
                )


def _validate_tool_call(tool_call: object) -> tuple[str, str, str]:
    if not isinstance(tool_call, Mapping):
        raise ValueError("LLM tool call must be an object")
    if tool_call.get("type") != "function":
        raise ValueError("LLM tool call must have type 'function'")

    call_id = tool_call.get("id")
    if not isinstance(call_id, str) or not call_id.strip():
        raise ValueError("LLM tool call must have a nonblank id")
    function = tool_call.get("function")
    if not isinstance(function, Mapping):
        raise ValueError("LLM tool call must contain a function object")

    name = function.get("name")
    if name not in _TOOL_ARGUMENTS:
        raise ValueError(f"Unknown graph tool '{name}'")
    arguments_text = function.get("arguments")
    if not isinstance(arguments_text, str):
        raise ValueError(f"Tool '{name}' arguments must be a JSON string")
    try:
        arguments = json.loads(arguments_text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Tool '{name}' arguments are not valid JSON") from error
    if not isinstance(arguments, dict):
        raise ValueError(f"Tool '{name}' arguments must be a JSON object")

    argument_name = _TOOL_ARGUMENTS[name]
    if set(arguments) != {argument_name}:
        raise ValueError(
            f"Tool '{name}' arguments must contain only '{argument_name}'"
        )
    argument = arguments[argument_name]
    if not isinstance(argument, str) or not argument.strip():
        raise ValueError(f"Tool '{name}' argument '{argument_name}' must be a nonblank string")
    return call_id, name, argument


def _run_retrieval_tool(
    retrieval: Neo4jGraphRetrieval,
    name: str,
    argument: str,
) -> list[OntologyObject]:
    tools = {
        "owners_for_service": retrieval.owners_for_service,
        "repositories_for_service": retrieval.repositories_for_service,
        "services_affected_by_incident": retrieval.services_affected_by_incident,
        "teams_for_person": retrieval.teams_for_person,
    }
    return tools[name](argument)


_TOOL_ARGUMENTS = {
    "owners_for_service": "service_name",
    "repositories_for_service": "service_name",
    "services_affected_by_incident": "incident_name",
    "teams_for_person": "person_name",
}

_GRAPH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "owners_for_service",
            "description": "Find Teams that own a Service.",
            "strict": True,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["service_name"],
                "properties": {"service_name": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "repositories_for_service",
            "description": "Find Repositories that implement a Service.",
            "strict": True,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["service_name"],
                "properties": {"service_name": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "services_affected_by_incident",
            "description": "Find Services affected by an Incident.",
            "strict": True,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["incident_name"],
                "properties": {"incident_name": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "teams_for_person",
            "description": "Find Teams that a Person belongs to.",
            "strict": True,
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["person_name"],
                "properties": {"person_name": {"type": "string"}},
            },
        },
    },
]

_AGENT_INSTRUCTIONS = """Answer the user's question only from graph tool results.
Use the provided tools when graph data is needed. Do not invent entities or relations.
If a tool returns an empty list, clearly say that the graph contains no matching result."""
