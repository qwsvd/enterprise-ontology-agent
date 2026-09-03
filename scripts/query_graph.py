"""Run fixed typed ontology retrieval queries against Neo4j."""

import argparse
import json

from enterprise_ontology_agent.infrastructure import Neo4jGraphRetrieval


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the Neo4j ontology graph")
    parser.add_argument(
        "operation",
        choices=["owners", "repositories", "affected-services", "teams"],
        help="Typed graph retrieval operation",
    )
    parser.add_argument("name", help="Service, Incident, or Person name")
    arguments = parser.parse_args()

    retrieval = Neo4jGraphRetrieval.from_environment()
    try:
        operations = {
            "owners": retrieval.owners_for_service,
            "repositories": retrieval.repositories_for_service,
            "affected-services": retrieval.services_affected_by_incident,
            "teams": retrieval.teams_for_person,
        }
        results = operations[arguments.operation](arguments.name)
    finally:
        retrieval.close()

    print(json.dumps([item.model_dump(mode="json") for item in results], indent=2))


if __name__ == "__main__":
    main()
