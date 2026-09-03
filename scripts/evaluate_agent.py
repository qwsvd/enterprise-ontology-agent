"""Run the live, deterministic graph-agent benchmark."""

import json
from pathlib import Path

from enterprise_ontology_agent.infrastructure import (
    GraphAgent,
    Neo4jGraphRetrieval,
    OpenAICompatibleClient,
    evaluate_cases,
    load_eval_cases,
)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    cases = load_eval_cases(project_root / "data" / "agent_eval_cases.json")
    retrieval = Neo4jGraphRetrieval.from_environment()
    try:
        agent = GraphAgent(OpenAICompatibleClient.from_environment(), retrieval)
        summary = evaluate_cases(cases, agent)
    finally:
        retrieval.close()

    output_path = project_root / "artifacts" / "agent_eval_results.json"
    output_path.parent.mkdir(exist_ok=True)
    output_path.write_text(
        json.dumps(summary.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    print(json.dumps(summary.model_dump(mode="json", exclude={"cases"}), indent=2))
    print(f"Wrote per-case results to {output_path}")


if __name__ == "__main__":
    main()
