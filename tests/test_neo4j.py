"""Unit tests for the Neo4j persistence adapter."""

from collections.abc import Iterator
from typing import Any

import pytest

from enterprise_ontology_agent.infrastructure import Neo4jRepository
from enterprise_ontology_agent.ontology import (
    ObjectType,
    OntologyObject,
    OntologyRelation,
    RelationType,
)


class FakeResult:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = records

    def single(self) -> dict[str, Any] | None:
        return self._records[0] if self._records else None

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self._records)


class FakeSession:
    def __init__(self, driver: "FakeDriver") -> None:
        self._driver = driver

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def run(self, query: str, **parameters: Any) -> FakeResult:
        self._driver.calls.append((query, parameters))
        records = self._driver.responses.pop(0) if self._driver.responses else []
        return FakeResult(records)


class FakeDriver:
    def __init__(self, responses: list[list[dict[str, Any]]] | None = None) -> None:
        self.responses = responses or []
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.databases: list[str] = []
        self.closed = False

    def session(self, *, database: str) -> FakeSession:
        self.databases.append(database)
        return FakeSession(self)

    def close(self) -> None:
        self.closed = True


def test_save_object_creates_new_object_with_parameterized_merge() -> None:
    driver = FakeDriver(responses=[[], [{"stored_type": "Person", "type_matches": True}]])
    repository = Neo4jRepository(driver=driver, database="neo4j")
    ontology_object = OntologyObject(
        id="person-1",
        name="Ada Lovelace",
        object_type=ObjectType.PERSON,
    )

    repository.save_object(ontology_object)

    constraint_query, _ = driver.calls[0]
    query, parameters = driver.calls[1]
    assert "IS UNIQUE" in constraint_query
    assert "MERGE (object:OntologyObject {id: $id})" in query
    assert "ON CREATE SET object.object_type = $object_type" in query
    assert "person-1" not in query
    assert "Ada Lovelace" not in query
    assert parameters == {
        "id": "person-1",
        "name": "Ada Lovelace",
        "object_type": "Person",
    }


def test_save_object_updates_name_when_type_is_unchanged() -> None:
    driver = FakeDriver(responses=[[], [{"stored_type": "Person", "type_matches": True}]])
    repository = Neo4jRepository(driver=driver, database="neo4j")

    repository.save_object(
        OntologyObject(
            id="person-1",
            name="Ada Byron",
            object_type=ObjectType.PERSON,
        )
    )

    query, parameters = driver.calls[1]
    assert "CASE WHEN type_matches" in query
    assert "SET object.name = $name" in query
    assert parameters["name"] == "Ada Byron"
    assert parameters["object_type"] == "Person"


def test_save_object_rejects_object_type_change() -> None:
    driver = FakeDriver(responses=[[], [{"stored_type": "Person", "type_matches": False}]])
    repository = Neo4jRepository(driver=driver, database="neo4j")

    with pytest.raises(
        ValueError,
        match=(
            "Object type mismatch for 'person-1': stored object is Person, "
            "incoming object is Team"
        ),
    ):
        repository.save_object(
            OntologyObject(
                id="person-1",
                name="Platform",
                object_type=ObjectType.TEAM,
            )
        )

    assert len(driver.calls) == 2


def test_get_object_deserializes_domain_object() -> None:
    driver = FakeDriver(
        responses=[
            [],
            [
                {
                    "object": {
                        "id": "service-1",
                        "name": "Catalog",
                        "object_type": "Service",
                    }
                }
            ],
        ]
    )
    repository = Neo4jRepository(driver=driver, database="neo4j")

    ontology_object = repository.get_object("service-1")

    assert ontology_object == OntologyObject(
        id="service-1",
        name="Catalog",
        object_type=ObjectType.SERVICE,
    )
    query, parameters = driver.calls[1]
    assert "$id" in query
    assert "service-1" not in query
    assert parameters == {"id": "service-1"}


@pytest.mark.parametrize(
    ("source_exists", "target_exists", "message"),
    [
        (False, True, "Source object 'person-1' does not exist"),
        (True, False, "Target object 'team-1' does not exist"),
    ],
)
def test_save_relation_rejects_missing_endpoints(
    source_exists: bool,
    target_exists: bool,
    message: str,
) -> None:
    driver = FakeDriver(
        responses=[
            [],
            [
                {
                    "source_exists": source_exists,
                    "target_exists": target_exists,
                }
            ],
        ]
    )
    repository = Neo4jRepository(driver=driver, database="neo4j")

    with pytest.raises(ValueError, match=message):
        repository.save_relation(_member_of_relation())

    assert len(driver.calls) == 2


def test_save_relation_uses_parameters_and_duplicate_safe_merge() -> None:
    driver = FakeDriver(
        responses=[
            [],
            [
                {
                    "source_exists": True,
                    "target_exists": True,
                    "source_type": "Person",
                    "target_type": "Team",
                }
            ],
            [],
        ]
    )
    repository = Neo4jRepository(driver=driver, database="neo4j")

    repository.save_relation(_member_of_relation())

    query, parameters = driver.calls[2]
    assert "MERGE (source)-[:MEMBER_OF]->(target)" in query
    assert "person-1" not in query
    assert "team-1" not in query
    assert parameters == {"source_id": "person-1", "target_id": "team-1"}


def test_save_relation_rejects_stored_source_type_mismatch() -> None:
    driver = FakeDriver(
        responses=[
            [],
            [
                {
                    "source_exists": True,
                    "target_exists": True,
                    "source_type": "Incident",
                    "target_type": "Team",
                }
            ],
        ]
    )
    repository = Neo4jRepository(driver=driver, database="neo4j")

    with pytest.raises(ValueError, match="Source type mismatch for 'person-1'"):
        repository.save_relation(_member_of_relation())

    assert len(driver.calls) == 2


def test_save_relation_rejects_stored_target_type_mismatch() -> None:
    driver = FakeDriver(
        responses=[
            [],
            [
                {
                    "source_exists": True,
                    "target_exists": True,
                    "source_type": "Person",
                    "target_type": "Repository",
                }
            ],
        ]
    )
    repository = Neo4jRepository(driver=driver, database="neo4j")

    with pytest.raises(ValueError, match="Target type mismatch for 'team-1'"):
        repository.save_relation(_member_of_relation())

    assert len(driver.calls) == 2


def test_get_neighbors_deserializes_objects_bidirectionally() -> None:
    driver = FakeDriver(
        responses=[
            [],
            [
                {
                    "neighbor": {
                        "id": "person-1",
                        "name": "Ada",
                        "object_type": "Person",
                    }
                },
                {
                    "neighbor": {
                        "id": "service-1",
                        "name": "Catalog",
                        "object_type": "Service",
                    }
                },
            ],
        ]
    )
    repository = Neo4jRepository(driver=driver, database="neo4j")

    neighbors = repository.get_neighbors("team-1")

    assert [neighbor.id for neighbor in neighbors] == ["person-1", "service-1"]
    query, parameters = driver.calls[1]
    assert "--(neighbor:OntologyObject)" in query
    assert "ORDER BY neighbor.id" in query
    assert parameters == {"id": "team-1"}


def _member_of_relation() -> OntologyRelation:
    return OntologyRelation(
        source_id="person-1",
        source_type=ObjectType.PERSON,
        relation_type=RelationType.MEMBER_OF,
        target_id="team-1",
        target_type=ObjectType.TEAM,
    )
