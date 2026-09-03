"""Ingest a JSON ontology dataset into Neo4j."""

import argparse
from pathlib import Path

from enterprise_ontology_agent.infrastructure import Neo4jRepository, ingest_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest ontology JSON into Neo4j")
    parser.add_argument("path", type=Path, help="Path to an ontology JSON file")
    arguments = parser.parse_args()

    repository = Neo4jRepository.from_environment()
    try:
        object_count, relation_count = ingest_json(arguments.path, repository)
    finally:
        repository.close()

    print(f"Ingested {object_count} objects and {relation_count} relations.")


if __name__ == "__main__":
    main()
