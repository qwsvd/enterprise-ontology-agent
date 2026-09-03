"""Tests for the in-memory ontology graph."""

import pytest

from enterprise_ontology_agent.ontology import (
    ObjectType,
    OntologyGraph,
    OntologyObject,
    OntologyRelation,
    RelationType,
)


def test_add_and_get_object() -> None:
    graph = OntologyGraph()
    person = OntologyObject(
        id="person-1",
        name="Ada Lovelace",
        object_type=ObjectType.PERSON,
    )

    graph.add_object(person)

    assert graph.get_object("person-1") == person
    assert graph.get_object("missing") is None


def test_duplicate_object_id_is_rejected() -> None:
    graph = OntologyGraph()
    graph.add_object(
        OntologyObject(id="team-1", name="Platform", object_type=ObjectType.TEAM)
    )

    duplicate = OntologyObject(
        id="team-1",
        name="Another Team",
        object_type=ObjectType.TEAM,
    )
    with pytest.raises(ValueError, match="Object with id 'team-1' already exists"):
        graph.add_object(duplicate)


def test_add_valid_relation() -> None:
    graph = OntologyGraph()
    graph.add_object(
        OntologyObject(id="person-1", name="Ada", object_type=ObjectType.PERSON)
    )
    graph.add_object(
        OntologyObject(id="team-1", name="Platform", object_type=ObjectType.TEAM)
    )

    graph.add_relation(
        OntologyRelation(
            source_id="person-1",
            source_type=ObjectType.PERSON,
            relation_type=RelationType.MEMBER_OF,
            target_id="team-1",
            target_type=ObjectType.TEAM,
        )
    )

    assert graph.get_neighbors("person-1") == [graph.get_object("team-1")]


def test_relation_rejects_missing_source() -> None:
    graph = OntologyGraph()
    graph.add_object(
        OntologyObject(id="team-1", name="Platform", object_type=ObjectType.TEAM)
    )
    relation = OntologyRelation(
        source_id="person-1",
        source_type=ObjectType.PERSON,
        relation_type=RelationType.MEMBER_OF,
        target_id="team-1",
        target_type=ObjectType.TEAM,
    )

    with pytest.raises(ValueError, match="Source object 'person-1' does not exist"):
        graph.add_relation(relation)


def test_relation_rejects_missing_target() -> None:
    graph = OntologyGraph()
    graph.add_object(
        OntologyObject(id="person-1", name="Ada", object_type=ObjectType.PERSON)
    )
    relation = OntologyRelation(
        source_id="person-1",
        source_type=ObjectType.PERSON,
        relation_type=RelationType.MEMBER_OF,
        target_id="team-1",
        target_type=ObjectType.TEAM,
    )

    with pytest.raises(ValueError, match="Target object 'team-1' does not exist"):
        graph.add_relation(relation)


def test_relation_rejects_source_type_mismatch() -> None:
    graph = OntologyGraph()
    graph.add_object(
        OntologyObject(id="person-1", name="Platform", object_type=ObjectType.TEAM)
    )
    graph.add_object(
        OntologyObject(id="team-1", name="Core", object_type=ObjectType.TEAM)
    )
    relation = OntologyRelation(
        source_id="person-1",
        source_type=ObjectType.PERSON,
        relation_type=RelationType.MEMBER_OF,
        target_id="team-1",
        target_type=ObjectType.TEAM,
    )

    with pytest.raises(ValueError, match="Source type mismatch for 'person-1'"):
        graph.add_relation(relation)


def test_relation_rejects_target_type_mismatch() -> None:
    graph = OntologyGraph()
    graph.add_object(
        OntologyObject(id="person-1", name="Ada", object_type=ObjectType.PERSON)
    )
    graph.add_object(
        OntologyObject(
            id="team-1",
            name="Repository",
            object_type=ObjectType.REPOSITORY,
        )
    )
    relation = OntologyRelation(
        source_id="person-1",
        source_type=ObjectType.PERSON,
        relation_type=RelationType.MEMBER_OF,
        target_id="team-1",
        target_type=ObjectType.TEAM,
    )

    with pytest.raises(ValueError, match="Target type mismatch for 'team-1'"):
        graph.add_relation(relation)


def test_neighbor_lookup_returns_incoming_and_outgoing_objects() -> None:
    graph = OntologyGraph()
    person = OntologyObject(
        id="person-1", name="Ada", object_type=ObjectType.PERSON
    )
    team = OntologyObject(id="team-1", name="Platform", object_type=ObjectType.TEAM)
    service = OntologyObject(
        id="service-1", name="Catalog", object_type=ObjectType.SERVICE
    )
    for ontology_object in (person, team, service):
        graph.add_object(ontology_object)

    graph.add_relation(
        OntologyRelation(
            source_id="person-1",
            source_type=ObjectType.PERSON,
            relation_type=RelationType.MEMBER_OF,
            target_id="team-1",
            target_type=ObjectType.TEAM,
        )
    )
    graph.add_relation(
        OntologyRelation(
            source_id="team-1",
            source_type=ObjectType.TEAM,
            relation_type=RelationType.OWNS,
            target_id="service-1",
            target_type=ObjectType.SERVICE,
        )
    )

    assert graph.get_neighbors("team-1") == [person, service]
    assert graph.get_neighbors("unknown") == []
