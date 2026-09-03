"""Ask the tool-calling graph agent a natural-language question."""

import argparse

from enterprise_ontology_agent.infrastructure import (
    GraphAgent,
    Neo4jGraphRetrieval,
    OpenAICompatibleClient,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the Neo4j graph agent")
    parser.add_argument("question", help="Natural-language question about the graph")
    arguments = parser.parse_args()

    retrieval = Neo4jGraphRetrieval.from_environment()
    try:
        agent = GraphAgent(OpenAICompatibleClient.from_environment(), retrieval)
        print(agent.answer(arguments.question))
    finally:
        retrieval.close()


if __name__ == "__main__":
    main()
