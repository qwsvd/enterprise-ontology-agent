"""Tests for LLM-backed ontology extraction without network access."""

import json

import pytest
from pydantic import ValidationError

from enterprise_ontology_agent.infrastructure import extract_ontology
from enterprise_ontology_agent.infrastructure import llm_extraction
from enterprise_ontology_agent.infrastructure.llm_extraction import (
    OpenAICompatibleClient,
    make_object_id,
)
from enterprise_ontology_agent.ontology import ObjectType


class FakeLLMClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.texts = []

    def extract(self, text: str) -> str:
        self.texts.append(text)
        return self.response if isinstance(self.response, str) else json.dumps(self.response)


def test_valid_extraction_creates_validated_models() -> None:
    client = FakeLLMClient(_valid_response())

    extraction = extract_ontology("Alice joined Payments.", client)

    assert [item.id for item in extraction.objects] == [
        "person-alice",
        "team-payments",
        "service-payment-api",
        "repository-payment-service",
        "incident-inc-204",
    ]
    assert all(item.source_type == "llm_extraction" for item in extraction.objects)
    assert len(extraction.relations) == 4
    assert extraction.relations[0].source_id == "person-alice"


def test_invalid_object_type_uses_domain_validation() -> None:
    response = _valid_response()
    response["objects"][0]["object_type"] = "Department"

    with pytest.raises(ValidationError):
        extract_ontology("text", FakeLLMClient(response))


def test_invalid_relation_domain_range_uses_domain_validation() -> None:
    response = _valid_response()
    response["relations"][0]["relation_type"] = "OWNS"

    with pytest.raises(ValidationError, match="Invalid relation"):
        extract_ontology("text", FakeLLMClient(response))


def test_relation_with_missing_object_is_rejected() -> None:
    response = _valid_response()
    response["objects"] = response["objects"][1:]

    with pytest.raises(ValueError, match=r"Relation source 'Alice' \(Person\)"):
        extract_ontology("text", FakeLLMClient(response))


def test_duplicate_objects_and_relations_are_deduplicated() -> None:
    response = _valid_response()
    response["objects"].append(response["objects"][0].copy())
    response["relations"].append(response["relations"][0].copy())

    extraction = extract_ontology("text", FakeLLMClient(response))

    assert len(extraction.objects) == 5
    assert len(extraction.relations) == 4


def test_object_ids_are_deterministic() -> None:
    assert make_object_id(ObjectType.TEAM, "Payments") == "team-payments"
    assert make_object_id(ObjectType.SERVICE, "Payment API") == "service-payment-api"


def test_malformed_llm_json_is_rejected() -> None:
    with pytest.raises(ValueError, match="LLM returned invalid JSON"):
        extract_ontology("text", FakeLLMClient("not json"))


def test_openai_compatible_client_requests_json_object(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = []

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, *args: object) -> bytes:
            return b'{"choices": [{"message": {"content": "{}"}}]}'

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        requests.append(request)
        return FakeResponse()

    monkeypatch.setattr(llm_extraction, "urlopen", fake_urlopen)

    client = OpenAICompatibleClient(
        api_key="test-key",
        base_url="https://api.example.test/v1",
        model="test-model",
    )

    assert client.extract("Alice joined Payments.") == "{}"
    payload = json.loads(requests[0].data)
    assert payload["response_format"] == {"type": "json_object"}
    assert "Each relation needs source_name" in payload["messages"][0]["content"]


def test_extraction_prompt_uses_canonical_names_for_type_descriptors() -> None:
    prompt = llm_extraction._EXTRACTION_INSTRUCTIONS

    assert "Payments team" in prompt
    assert "payment-service repository" in prompt
    assert "Notification Service remains Notification Service" in prompt


def _valid_response() -> dict[str, object]:
    return {
        "objects": [
            {"name": "Alice", "object_type": "Person"},
            {"name": "Payments", "object_type": "Team"},
            {"name": "Payment API", "object_type": "Service"},
            {"name": "payment-service", "object_type": "Repository"},
            {"name": "INC-204", "object_type": "Incident"},
        ],
        "relations": [
            {
                "source_name": "Alice",
                "source_type": "Person",
                "relation_type": "MEMBER_OF",
                "target_name": "Payments",
                "target_type": "Team",
            },
            {
                "source_name": "Payments",
                "source_type": "Team",
                "relation_type": "OWNS",
                "target_name": "Payment API",
                "target_type": "Service",
            },
            {
                "source_name": "payment-service",
                "source_type": "Repository",
                "relation_type": "IMPLEMENTS",
                "target_name": "Payment API",
                "target_type": "Service",
            },
            {
                "source_name": "INC-204",
                "source_type": "Incident",
                "relation_type": "AFFECTS",
                "target_name": "Payment API",
                "target_type": "Service",
            },
        ],
    }
