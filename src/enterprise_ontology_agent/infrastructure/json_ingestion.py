"""Load validated ontology data from JSON files."""

import json
from pathlib import Path

from enterprise_ontology_agent.infrastructure.neo4j import Neo4jRepository
from enterprise_ontology_agent.ontology import OntologyObject, OntologyRelation


def ingest_json(path: Path, repository: Neo4jRepository) -> tuple[int, int]:
    """Validate and persist the objects and relations in a JSON dataset."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in '{path}': {error.msg}") from error

    if not isinstance(data, dict):
        raise ValueError("JSON dataset must be an object")
    if not isinstance(data.get("objects"), list):
        raise ValueError("JSON dataset must contain an 'objects' list")
    if not isinstance(data.get("relations"), list):
        raise ValueError("JSON dataset must contain a 'relations' list")

    objects = [OntologyObject.model_validate(item) for item in data["objects"]]
    relations = [OntologyRelation.model_validate(item) for item in data["relations"]]

    for ontology_object in objects:
        repository.save_object(ontology_object)
    for relation in relations:
        repository.save_relation(relation)

    return len(objects), len(relations)
