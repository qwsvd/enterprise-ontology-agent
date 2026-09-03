"""Optional live integration test for the Neo4j persistence adapter."""

import os

import pytest

from enterprise_ontology_agent.infrastructure import Neo4jRepository
from enterprise_ontology_agent.ontology import (
    ObjectType,
    OntologyObject,
    OntologyRelation,
    RelationType,
)


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_NEO4J_INTEGRATION") != "1",
    reason="set RUN_NEO4J_INTEGRATION=1 to run against a real Neo4j instance",
)


def test_real_neo4j_persists_objects_and_relations() -> None:
    repository = Neo4jRepository.from_environment()
    team = OntologyObject(
        id="integration-team-payments",
        name="Integration Payments",
        object_type=ObjectType.TEAM,
    )
    service = OntologyObject(
        id="integration-service-payment-api",
        name="Integration Payment API",
        object_type=ObjectType.SERVICE,
    )
    relation = OntologyRelation(
        source_id=team.id,
        source_type=ObjectType.TEAM,
        relation_type=RelationType.OWNS,
        target_id=service.id,
        target_type=ObjectType.SERVICE,
    )

    try:
        repository.save_object(team)
        repository.save_object(service)
        repository.save_relation(relation)

        assert repository.get_object(service.id) == service
        assert {neighbor.id for neighbor in repository.get_neighbors(service.id)} >= {
            team.id
        }
    finally:
        repository.close()
