"""Extract validated ontology JSON from a UTF-8 text file."""

import argparse
import json
from pathlib import Path

from enterprise_ontology_agent.infrastructure import (
    Neo4jRepository,
    OpenAICompatibleClient,
    extract_ontology,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract ontology data from text")
    parser.add_argument("path", type=Path, help="Path to a UTF-8 text file")
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist validated objects and relations to Neo4j",
    )
    arguments = parser.parse_args()

    text = arguments.path.read_text(encoding="utf-8")
    extraction = extract_ontology(text, OpenAICompatibleClient.from_environment())

    if arguments.persist:
        repository = Neo4jRepository.from_environment()
        try:
            for ontology_object in extraction.objects:
                repository.save_object(ontology_object)
            for relation in extraction.relations:
                repository.save_relation(relation)
        finally:
            repository.close()

    print(
        json.dumps(
            {
                "objects": [item.model_dump(mode="json") for item in extraction.objects],
                "relations": [item.model_dump(mode="json") for item in extraction.relations],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
