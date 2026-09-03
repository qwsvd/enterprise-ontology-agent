"""Typed read-only retrieval from the Neo4j ontology graph."""

import os
from collections.abc import Mapping
from typing import Any

from neo4j import Driver, GraphDatabase

from enterprise_ontology_agent.ontology import ObjectType, OntologyObject


_OWNERS_FOR_SERVICE = """
MATCH (object:OntologyObject {object_type: 'Team'})-[:OWNS]->
      (:OntologyObject {name: $name, object_type: 'Service'})
RETURN DISTINCT object
ORDER BY object.id
"""

_REPOSITORIES_FOR_SERVICE = """
MATCH (object:OntologyObject {object_type: 'Repository'})-[:IMPLEMENTS]->
      (:OntologyObject {name: $name, object_type: 'Service'})
RETURN DISTINCT object
ORDER BY object.id
"""

_SERVICES_FOR_INCIDENT = """
MATCH (:OntologyObject {name: $name, object_type: 'Incident'})-[:AFFECTS]->
      (object:OntologyObject {object_type: 'Service'})
RETURN DISTINCT object
ORDER BY object.id
"""

_TEAMS_FOR_PERSON = """
MATCH (:OntologyObject {name: $name, object_type: 'Person'})-[:MEMBER_OF]->
      (object:OntologyObject {object_type: 'Team'})
RETURN DISTINCT object
ORDER BY object.id
"""


class Neo4jGraphRetrieval:
    """Run fixed typed retrieval queries against an ontology graph."""

    def __init__(self, driver: Driver, database: str) -> None:
        self._driver = driver
        self._database = database

    @classmethod
    def from_environment(cls) -> "Neo4jGraphRetrieval":
        """Create a retrieval client from required Neo4j environment variables."""
        names = (
            "NEO4J_URI",
            "NEO4J_USERNAME",
            "NEO4J_PASSWORD",
            "NEO4J_DATABASE",
        )
        values = {name: os.environ.get(name) for name in names}
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(
                "Missing required Neo4j environment variables: " + ", ".join(missing)
            )
        driver = GraphDatabase.driver(
            values["NEO4J_URI"],
            auth=(values["NEO4J_USERNAME"], values["NEO4J_PASSWORD"]),
        )
        return cls(driver=driver, database=values["NEO4J_DATABASE"])

    def close(self) -> None:
        """Close the underlying Neo4j driver."""
        self._driver.close()

    def owners_for_service(self, service_name: str) -> list[OntologyObject]:
        """Return Teams that own the named Service."""
        return self._query_objects(_OWNERS_FOR_SERVICE, service_name)

    def repositories_for_service(self, service_name: str) -> list[OntologyObject]:
        """Return Repositories that implement the named Service."""
        return self._query_objects(_REPOSITORIES_FOR_SERVICE, service_name)

    def services_affected_by_incident(self, incident_name: str) -> list[OntologyObject]:
        """Return Services affected by the named Incident."""
        return self._query_objects(_SERVICES_FOR_INCIDENT, incident_name)

    def teams_for_person(self, person_name: str) -> list[OntologyObject]:
        """Return Teams that the named Person belongs to."""
        return self._query_objects(_TEAMS_FOR_PERSON, person_name)

    def _query_objects(self, query: str, name: str) -> list[OntologyObject]:
        with self._driver.session(database=self._database) as session:
            records = session.run(query, name=name)
            return [self._object_from_node(record["object"]) for record in records]

    @staticmethod
    def _object_from_node(node: Mapping[str, Any]) -> OntologyObject:
        return OntologyObject(
            id=node["id"],
            name=node["name"],
            object_type=ObjectType(node["object_type"]),
            source_url=node.get("source_url"),
            source_type=node.get("source_type"),
            external_id=node.get("external_id"),
        )
