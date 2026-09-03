"""Ingest one public GitHub repository into Neo4j."""

import argparse
import os

from enterprise_ontology_agent.infrastructure import (
    Neo4jRepository,
    ingest_github_repository,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a GitHub repository into Neo4j")
    parser.add_argument("repository", help="GitHub repository in owner/repo format")
    arguments = parser.parse_args()

    repository = Neo4jRepository.from_environment()
    try:
        result = ingest_github_repository(
            arguments.repository,
            repository,
            token=os.environ.get("GITHUB_TOKEN"),
        )
    finally:
        repository.close()

    print(
        f"Ingested {result.ontology_object.name}: {result.issue_count} recent "
        f"issues and {result.pull_request_count} recent pull requests fetched."
    )


if __name__ == "__main__":
    main()
