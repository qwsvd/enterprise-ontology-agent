"""Extract validated ontology models from natural-language text."""

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.request import Request, urlopen

from enterprise_ontology_agent.ontology import (
    ObjectType,
    OntologyObject,
    OntologyRelation,
)


class LLMClient(Protocol):
    """Small interface for requesting a structured extraction."""

    def extract(self, text: str) -> str:
        """Return an ontology extraction as a JSON string."""


@dataclass(frozen=True)
class OntologyExtraction:
    """Validated objects and relations extracted from text."""

    objects: list[OntologyObject]
    relations: list[OntologyRelation]


class OpenAICompatibleClient:
    """Minimal Chat Completions client for OpenAI-compatible APIs."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    @classmethod
    def from_environment(cls) -> "OpenAICompatibleClient":
        """Create a client from required LLM environment variables."""
        names = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")
        values = {name: os.environ.get(name) for name in names}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(
                "Missing required LLM environment variables: " + ", ".join(missing)
            )
        return cls(
            api_key=values["LLM_API_KEY"],
            base_url=values["LLM_BASE_URL"],
            model=values["LLM_MODEL"],
        )

    def extract(self, text: str) -> str:
        """Request structured ontology JSON from the configured LLM."""
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _EXTRACTION_INSTRUCTIONS},
                {"role": "user", "content": text},
            ],
            "response_format": {"type": "json_object"},
        }
        request = Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            response_data = json.load(response)

        try:
            content = response_data["choices"][0]["message"]["content"]
        except (IndexError, KeyError, TypeError) as error:
            raise ValueError("LLM response did not contain a completion message") from error
        if not isinstance(content, str):
            raise ValueError("LLM response content must be a JSON string")
        return content

    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Send an OpenAI-compatible function-calling chat request."""
        payload = {
            "model": self._model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "thinking": {"type": "disabled"},
        }
        request = Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            response_data = json.load(response)

        try:
            message = response_data["choices"][0]["message"]
        except (IndexError, KeyError, TypeError) as error:
            raise ValueError("LLM response did not contain a completion message") from error
        if not isinstance(message, dict):
            raise ValueError("LLM completion message must be an object")
        return message


def extract_ontology(text: str, client: LLMClient) -> OntologyExtraction:
    """Convert one LLM JSON response into validated ontology domain models."""
    try:
        data = json.loads(client.extract(text))
    except json.JSONDecodeError as error:
        raise ValueError(f"LLM returned invalid JSON: {error.msg}") from error

    if not isinstance(data, dict):
        raise ValueError("LLM JSON must be an object")
    if not isinstance(data.get("objects"), list):
        raise ValueError("LLM JSON must contain an 'objects' list")
    if not isinstance(data.get("relations"), list):
        raise ValueError("LLM JSON must contain a 'relations' list")

    objects_by_key: dict[tuple[ObjectType, str], OntologyObject] = {}
    for item in data["objects"]:
        raw_object = _mapping(item, "object")
        candidate = OntologyObject(
            id="pending",
            name=raw_object.get("name"),
            object_type=raw_object.get("object_type"),
            source_type="llm_extraction",
        )
        key = (candidate.object_type, normalize_object_name(candidate.name))
        objects_by_key.setdefault(
            key,
            OntologyObject(
                id=make_object_id(candidate.object_type, candidate.name),
                name=candidate.name,
                object_type=candidate.object_type,
                source_type="llm_extraction",
            ),
        )

    relations_by_key: dict[
        tuple[str, ObjectType, str, str, ObjectType], OntologyRelation
    ] = {}
    for item in data["relations"]:
        raw_relation = _mapping(item, "relation")
        candidate = OntologyRelation(
            source_id="source",
            source_type=raw_relation.get("source_type"),
            relation_type=raw_relation.get("relation_type"),
            target_id="target",
            target_type=raw_relation.get("target_type"),
        )
        source_name = raw_relation.get("source_name")
        target_name = raw_relation.get("target_name")
        source = objects_by_key.get(
            (candidate.source_type, normalize_object_name(source_name))
        )
        target = objects_by_key.get(
            (candidate.target_type, normalize_object_name(target_name))
        )
        if source is None:
            raise ValueError(
                f"Relation source '{source_name}' ({candidate.source_type.value}) "
                "is not in the extracted objects"
            )
        if target is None:
            raise ValueError(
                f"Relation target '{target_name}' ({candidate.target_type.value}) "
                "is not in the extracted objects"
            )

        relation = OntologyRelation(
            source_id=source.id,
            source_type=candidate.source_type,
            relation_type=candidate.relation_type,
            target_id=target.id,
            target_type=candidate.target_type,
        )
        relation_key = (
            relation.source_id,
            relation.source_type,
            relation.relation_type.value,
            relation.target_id,
            relation.target_type,
        )
        relations_by_key.setdefault(relation_key, relation)

    return OntologyExtraction(
        objects=list(objects_by_key.values()),
        relations=list(relations_by_key.values()),
    )


def make_object_id(object_type: ObjectType, name: str) -> str:
    """Create a deterministic ID from an object type and normalized name."""
    return f"{object_type.value.lower()}-{normalize_object_name(name)}"


def normalize_object_name(name: object) -> str:
    """Normalize an object name for deterministic identifiers and lookups."""
    if not isinstance(name, str):
        raise ValueError("Object and relation names must be strings")
    normalized = "".join(
        character.lower() if character.isalnum() else "-" for character in name
    )
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("Object and relation names must contain letters or numbers")
    return normalized


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Each extracted {label} must be a JSON object")
    return value


_EXTRACTION_INSTRUCTIONS = """Extract only explicitly stated enterprise ontology facts.
Return JSON with objects and relations. Each object needs name and object_type.
Each relation needs source_name, source_type, relation_type, target_name, and target_type.
Allowed object types: Person, Team, Service, Repository, Incident.
Allowed relations: Person MEMBER_OF Team; Team OWNS Service; Repository IMPLEMENTS Service; Incident AFFECTS Service.
Use canonical entity names: exclude a generic type word when it only describes the ontology type.
For example, emit Payments as a Team (not Payments team), and payment-service as a Repository (not payment-service repository).
Keep a type word when it is part of the meaningful name: Notification Service remains Notification Service.
Do not create IDs, provenance, unstated objects, or unstated relations."""
