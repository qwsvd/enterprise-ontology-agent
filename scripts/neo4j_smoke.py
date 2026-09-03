"""Persist and verify a small enterprise ontology dataset in Neo4j."""

from enterprise_ontology_agent.infrastructure import Neo4jRepository
from enterprise_ontology_agent.ontology import (
    ObjectType,
    OntologyObject,
    OntologyRelation,
    RelationType,
)


PAYMENTS_ID = "team-payments"
PAYMENT_API_ID = "service-payment-api"
PAYMENT_SERVICE_ID = "repository-payment-service"
INCIDENT_ID = "incident-inc-204"

DEMO_OBJECTS = (
    OntologyObject(id=PAYMENTS_ID, name="Payments", object_type=ObjectType.TEAM),
    OntologyObject(
        id=PAYMENT_API_ID,
        name="Payment API",
        object_type=ObjectType.SERVICE,
    ),
    OntologyObject(
        id=PAYMENT_SERVICE_ID,
        name="payment-service",
        object_type=ObjectType.REPOSITORY,
    ),
    OntologyObject(
        id=INCIDENT_ID,
        name="INC-204",
        object_type=ObjectType.INCIDENT,
    ),
)

DEMO_RELATIONS = (
    OntologyRelation(
        source_id=PAYMENTS_ID,
        source_type=ObjectType.TEAM,
        relation_type=RelationType.OWNS,
        target_id=PAYMENT_API_ID,
        target_type=ObjectType.SERVICE,
    ),
    OntologyRelation(
        source_id=PAYMENT_SERVICE_ID,
        source_type=ObjectType.REPOSITORY,
        relation_type=RelationType.IMPLEMENTS,
        target_id=PAYMENT_API_ID,
        target_type=ObjectType.SERVICE,
    ),
    OntologyRelation(
        source_id=INCIDENT_ID,
        source_type=ObjectType.INCIDENT,
        relation_type=RelationType.AFFECTS,
        target_id=PAYMENT_API_ID,
        target_type=ObjectType.SERVICE,
    ),
)


def main() -> None:
    repository = Neo4jRepository.from_environment()
    try:
        for ontology_object in DEMO_OBJECTS:
            repository.save_object(ontology_object)
        for relation in DEMO_RELATIONS:
            repository.save_relation(relation)

        for expected_object in DEMO_OBJECTS:
            if repository.get_object(expected_object.id) != expected_object:
                raise RuntimeError(f"Could not read back '{expected_object.id}'")

        neighbor_ids = {neighbor.id for neighbor in repository.get_neighbors(PAYMENT_API_ID)}
        expected_neighbor_ids = {
            PAYMENTS_ID,
            PAYMENT_SERVICE_ID,
            INCIDENT_ID,
        }
        if not expected_neighbor_ids.issubset(neighbor_ids):
            raise RuntimeError("Payment API is missing expected direct neighbors")
    finally:
        repository.close()

    repository = Neo4jRepository.from_environment()
    try:
        payment_api = repository.get_object(PAYMENT_API_ID)
        if payment_api != DEMO_OBJECTS[1]:
            raise RuntimeError("Payment API was not persisted after reconnecting")
    finally:
        repository.close()

    print("Neo4j smoke test passed: 4 objects, 3 relations, and Payment API verified.")


if __name__ == "__main__":
    main()
