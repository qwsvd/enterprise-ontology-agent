"""Tests for JSON ontology ingestion."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from enterprise_ontology_agent.infrastructure import ingest_json
from enterprise_ontology_agent.ontology import ObjectType, RelationType


class FakeRepository:
    def __init__(self) -> None:
        self.objects = []
        self.relations = []

    def save_object(self, ontology_object: object) -> None:
        self.objects.append(ontology_object)

    def save_relation(self, relation: object) -> None:
        self.relations.append(relation)


def test_ingests_valid_json_and_persists_models(tmp_path: Path) -> None:
    path = _write_dataset(tmp_path, _valid_dataset())
    repository = FakeRepository()

    object_count, relation_count = ingest_json(path, repository)  # type: ignore[arg-type]

    assert (object_count, relation_count) == (2, 1)
    assert repository.objects[0].object_type is ObjectType.TEAM
    assert repository.relations[0].relation_type is RelationType.OWNS


def test_invalid_object_type_uses_domain_validation(tmp_path: Path) -> None:
    dataset = _valid_dataset()
    dataset["objects"][0]["object_type"] = "Department"

    with pytest.raises(ValidationError):
        ingest_json(_write_dataset(tmp_path, dataset), FakeRepository())  # type: ignore[arg-type]


def test_invalid_relation_uses_domain_validation(tmp_path: Path) -> None:
    dataset = _valid_dataset()
    dataset["relations"][0]["relation_type"] = "MEMBER_OF"

    with pytest.raises(ValidationError, match="Invalid relation"):
        ingest_json(_write_dataset(tmp_path, dataset), FakeRepository())  # type: ignore[arg-type]


def test_malformed_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid JSON"):
        ingest_json(path, FakeRepository())  # type: ignore[arg-type]


def _write_dataset(tmp_path: Path, dataset: dict[str, object]) -> Path:
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")
    return path


def _valid_dataset() -> dict[str, object]:
    return {
        "objects": [
            {"id": "team-1", "name": "Platform", "object_type": "Team"},
            {"id": "service-1", "name": "Catalog", "object_type": "Service"},
        ],
        "relations": [
            {
                "source_id": "team-1",
                "source_type": "Team",
                "relation_type": "OWNS",
                "target_id": "service-1",
                "target_type": "Service",
            }
        ],
    }
