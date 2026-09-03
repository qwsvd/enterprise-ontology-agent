"""Neo4j persistence for the enterprise ontology domain."""

import os
from collections.abc import Mapping
from typing import Any

from neo4j import Driver, GraphDatabase

from enterprise_ontology_agent.ontology import (
    ObjectType,
    OntologyObject,
    OntologyRelation,
    RelationType,
)


_CREATE_ID_CONSTRAINT = """
CREATE CONSTRAINT ontology_object_id IF NOT EXISTS
FOR (object:OntologyObject)
REQUIRE object.id IS UNIQUE
"""

_SAVE_OBJECT = """
MERGE (object:OntologyObject {id: $id})
ON CREATE SET object.object_type = $object_type
WITH object, object.object_type = $object_type AS type_matches
FOREACH (_ IN CASE WHEN type_matches THEN [1] ELSE [] END |
    SET object.name = $name,
        object.source_url = $source_url,
        object.source_type = $source_type,
        object.external_id = $external_id
)
RETURN object.object_type AS stored_type, type_matches
"""

_GET_OBJECT = """
MATCH (object:OntologyObject {id: $id})
RETURN object
"""

_CHECK_ENDPOINTS = """
OPTIONAL MATCH (source:OntologyObject {id: $source_id})
OPTIONAL MATCH (target:OntologyObject {id: $target_id})
RETURN source IS NOT NULL AS source_exists,
       target IS NOT NULL AS target_exists,
       source.object_type AS source_type,
       target.object_type AS target_type
"""

_GET_NEIGHBORS = """
MATCH (object:OntologyObject {id: $id})--(neighbor:OntologyObject)
RETURN DISTINCT neighbor
ORDER BY neighbor.id
"""

_SAVE_RELATION_QUERIES = {
    relation_type: f"""
MATCH (source:OntologyObject {{id: $source_id}})
MATCH (target:OntologyObject {{id: $target_id}})
MERGE (source)-[:{relation_type.value}]->(target)
"""
    for relation_type in RelationType
}


class Neo4jRepository:
    """Persist ontology objects and relations in Neo4j."""

    def __init__(self, driver: Driver, database: str) -> None:
        self._driver = driver
        self._database = database
        with self._driver.session(database=self._database) as session:
            session.run(_CREATE_ID_CONSTRAINT)

    @classmethod
    def from_environment(cls) -> "Neo4jRepository":
        """Create a repository from required Neo4j environment variables."""
        variable_names = (
            "NEO4J_URI",
            "NEO4J_USERNAME",
            "NEO4J_PASSWORD",
            "NEO4J_DATABASE",
        )
        values = {name: os.environ.get(name) for name in variable_names}
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

    def save_object(self, ontology_object: OntologyObject) -> None:
        """Create or update an ontology object without duplicating its ID."""
        with self._driver.session(database=self._database) as session:
            record = session.run(
                _SAVE_OBJECT,
                id=ontology_object.id,
                name=ontology_object.name,
                object_type=ontology_object.object_type.value,
                source_url=ontology_object.source_url,
                source_type=ontology_object.source_type,
                external_id=ontology_object.external_id,
            ).single()

        if record is None or not record["type_matches"]:
            stored_type = record["stored_type"] if record is not None else "unknown"
            raise ValueError(
                f"Object type mismatch for '{ontology_object.id}': stored object is "
                f"{stored_type}, incoming object is {ontology_object.object_type.value}"
            )

    def get_object(self, object_id: str) -> OntologyObject | None:
        """Return an ontology object by ID, or None when it does not exist."""
        with self._driver.session(database=self._database) as session:
            record = session.run(_GET_OBJECT, id=object_id).single()

        if record is None:
            return None
        return self._object_from_node(record["object"])

    def save_relation(self, relation: OntologyRelation) -> None:
        """Persist a relation after verifying that both endpoints exist."""
        parameters = {
            "source_id": relation.source_id,
            "target_id": relation.target_id,
        }
        with self._driver.session(database=self._database) as session:
            endpoints = session.run(_CHECK_ENDPOINTS, **parameters).single()
            if endpoints is None or not endpoints["source_exists"]:
                raise ValueError(
                    f"Source object '{relation.source_id}' does not exist"
                )
            if not endpoints["target_exists"]:
                raise ValueError(
                    f"Target object '{relation.target_id}' does not exist"
                )
            if endpoints["source_type"] != relation.source_type.value:
                raise ValueError(
                    f"Source type mismatch for '{relation.source_id}': stored object is "
                    f"{endpoints['source_type']}, relation expects "
                    f"{relation.source_type.value}"
                )
            if endpoints["target_type"] != relation.target_type.value:
                raise ValueError(
                    f"Target type mismatch for '{relation.target_id}': stored object is "
                    f"{endpoints['target_type']}, relation expects "
                    f"{relation.target_type.value}"
                )

            session.run(_SAVE_RELATION_QUERIES[relation.relation_type], **parameters)

    def get_neighbors(self, object_id: str) -> list[OntologyObject]:
        """Return directly connected objects in a stable order."""
        with self._driver.session(database=self._database) as session:
            records = session.run(_GET_NEIGHBORS, id=object_id)
            return [self._object_from_node(record["neighbor"]) for record in records]

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
