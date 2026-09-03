"""Tests for the enterprise ontology domain model."""

import pytest
from pydantic import ValidationError

from enterprise_ontology_agent.ontology import (
    ObjectType,
    OntologyObject,
    OntologyRelation,
    RelationType,
)


def test_valid_object() -> None:
    ontology_object = OntologyObject(
        id="person-1",
        name="Ada Lovelace",
        object_type=ObjectType.PERSON,
    )

    assert ontology_object.object_type is ObjectType.PERSON


@pytest.mark.parametrize("field", ["id", "name"])
def test_object_rejects_blank_required_text(field: str) -> None:
    values = {
        "id": "person-1",
        "name": "Ada Lovelace",
        "object_type": ObjectType.PERSON,
    }
    values[field] = "   "

    with pytest.raises(ValidationError, match="must not be blank"):
        OntologyObject(**values)


def test_object_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        OntologyObject(id="object-1", name="Unknown", object_type="Unknown")


@pytest.mark.parametrize(
    ("source_type", "relation_type", "target_type"),
    [
        (ObjectType.PERSON, RelationType.MEMBER_OF, ObjectType.TEAM),
        (ObjectType.TEAM, RelationType.OWNS, ObjectType.SERVICE),
        (ObjectType.REPOSITORY, RelationType.IMPLEMENTS, ObjectType.SERVICE),
        (ObjectType.INCIDENT, RelationType.AFFECTS, ObjectType.SERVICE),
    ],
)
def test_valid_relations(
    source_type: ObjectType,
    relation_type: RelationType,
    target_type: ObjectType,
) -> None:
    relation = OntologyRelation(
        source_id="source-1",
        source_type=source_type,
        relation_type=relation_type,
        target_id="target-1",
        target_type=target_type,
    )

    assert relation.relation_type is relation_type


@pytest.mark.parametrize(
    ("source_type", "relation_type", "target_type"),
    [
        (ObjectType.INCIDENT, RelationType.OWNS, ObjectType.PERSON),
        (ObjectType.TEAM, RelationType.MEMBER_OF, ObjectType.REPOSITORY),
        (ObjectType.SERVICE, RelationType.IMPLEMENTS, ObjectType.PERSON),
    ],
)
def test_invalid_relation_combinations_have_clear_errors(
    source_type: ObjectType,
    relation_type: RelationType,
    target_type: ObjectType,
) -> None:
    expected_message = (
        f"Invalid relation: {source_type.value} "
        f"{relation_type.value} {target_type.value}"
    )

    with pytest.raises(ValidationError, match=expected_message):
        OntologyRelation(
            source_id="source-1",
            source_type=source_type,
            relation_type=relation_type,
            target_id="target-1",
            target_type=target_type,
        )
