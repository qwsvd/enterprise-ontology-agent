"""Unit tests for typed Neo4j graph retrieval."""

from collections.abc import Iterator
from typing import Any

from enterprise_ontology_agent.infrastructure import Neo4jGraphRetrieval
from enterprise_ontology_agent.ontology import ObjectType, OntologyObject


class FakeSession:
    def __init__(self, driver: "FakeDriver") -> None:
        self._driver = driver

    def __enter__(self) -> "FakeSession":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def run(self, query: str, **parameters: Any) -> list[dict[str, Any]]:
        self._driver.calls.append((query, parameters))
        return self._driver.responses.pop(0)


class FakeDriver:
    def __init__(self, responses: list[list[dict[str, Any]]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def session(self, *, database: str) -> FakeSession:
        return FakeSession(self)

    def close(self) -> None:
        self.closed = True


def test_owner_lookup_is_parameterized_and_preserves_provenance() -> None:
    driver = FakeDriver([[_record(_object("team-payments", "Payments", "Team"))]])
    retrieval = Neo4jGraphRetrieval(driver=driver, database="neo4j")

    results = retrieval.owners_for_service("Payment API")

    assert results == [
        OntologyObject(
            id="team-payments",
            name="Payments",
            object_type=ObjectType.TEAM,
            source_url="https://example.test/teams/payments",
            source_type="example",
            external_id="team-1",
        )
    ]
    query, parameters = driver.calls[0]
    assert "[:OWNS]" in query
    assert "$name" in query
    assert "Payment API" not in query
    assert "RETURN DISTINCT object" in query
    assert "ORDER BY object.id" in query
    assert parameters == {"name": "Payment API"}


def test_repository_lookup() -> None:
    driver = FakeDriver([[_record(_object("repository-payment", "payment-service", "Repository"))]])
    retrieval = Neo4jGraphRetrieval(driver=driver, database="neo4j")

    assert [item.name for item in retrieval.repositories_for_service("Payment API")] == [
        "payment-service"
    ]
    assert "[:IMPLEMENTS]" in driver.calls[0][0]


def test_affected_service_lookup() -> None:
    driver = FakeDriver([[_record(_object("service-payment-api", "Payment API", "Service"))]])
    retrieval = Neo4jGraphRetrieval(driver=driver, database="neo4j")

    assert [item.name for item in retrieval.services_affected_by_incident("INC-204")] == [
        "Payment API"
    ]
    assert "[:AFFECTS]" in driver.calls[0][0]


def test_team_lookup() -> None:
    driver = FakeDriver([[_record(_object("team-payments", "Payments", "Team"))]])
    retrieval = Neo4jGraphRetrieval(driver=driver, database="neo4j")

    assert [item.name for item in retrieval.teams_for_person("Alice")] == ["Payments"]
    assert "[:MEMBER_OF]" in driver.calls[0][0]


def test_no_results_returns_empty_list() -> None:
    driver = FakeDriver([[]])
    retrieval = Neo4jGraphRetrieval(driver=driver, database="neo4j")

    assert retrieval.owners_for_service("Unknown") == []


def test_results_keep_database_order() -> None:
    driver = FakeDriver(
        [
            [
                _record(_object("repository-a", "a-service", "Repository")),
                _record(_object("repository-b", "b-service", "Repository")),
            ]
        ]
    )
    retrieval = Neo4jGraphRetrieval(driver=driver, database="neo4j")

    assert [item.id for item in retrieval.repositories_for_service("Payment API")] == [
        "repository-a",
        "repository-b",
    ]
    assert "ORDER BY object.id" in driver.calls[0][0]


def _record(node: dict[str, str]) -> dict[str, dict[str, str]]:
    return {"object": node}


def _object(object_id: str, name: str, object_type: str) -> dict[str, str]:
    return {
        "id": object_id,
        "name": name,
        "object_type": object_type,
        "source_url": "https://example.test/teams/payments",
        "source_type": "example",
        "external_id": "team-1",
    }
