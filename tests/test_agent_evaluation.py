"""Tests for deterministic graph-agent evaluation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from enterprise_ontology_agent.infrastructure.agent_evaluation import (
    EvalCase,
    _percentile,
    evaluate_cases,
    load_eval_cases,
)
from enterprise_ontology_agent.infrastructure.graph_agent import AgentRun, AgentToolCall


class FakeAgent:
    def __init__(self, runs: dict[str, AgentRun | Exception]) -> None:
        self.runs = runs

    def run(self, question: str) -> AgentRun:
        outcome = self.runs[question]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _case(**overrides: object) -> EvalCase:
    values: dict[str, object] = {
        "id": "case-1",
        "question": "Who owns Payment API?",
        "expected_tool": "owners_for_service",
        "expected_argument": "Payment API",
        "expected_entities": ["Payments"],
        "expect_no_result": False,
    }
    values.update(overrides)
    return EvalCase.model_validate(values)


def _run(
    question: str,
    answer: str = "Payments owns Payment API.",
    tool_name: str = "owners_for_service",
    argument: str = "Payment API",
    result_count: int = 1,
) -> AgentRun:
    return AgentRun(
        question=question,
        final_answer=answer,
        tool_calls=[
            AgentToolCall(
                tool_name=tool_name,
                argument=argument,
                result_count=result_count,
                result_ids=["team-payments"] if result_count else [],
                result_names=["Payments"] if result_count else [],
            )
        ],
    )


def _evaluate(case: EvalCase, run: AgentRun | Exception):
    return evaluate_cases([case], FakeAgent({case.question: run}), clock=_clock())


def _clock():
    values = iter([10.0, 10.25])
    return lambda: next(values)


def test_tool_selection_and_argument_metrics_are_correct() -> None:
    case = _case()

    result = _evaluate(case, _run(case.question)).cases[0]

    assert result.tool_selection_correct is True
    assert result.argument_correct is True


def test_wrong_tool_and_argument_are_detected() -> None:
    case = _case()

    result = _evaluate(
        case,
        _run(case.question, tool_name="repositories_for_service", argument="Other API"),
    ).cases[0]

    assert result.tool_selection_correct is False
    assert result.argument_correct is False


def test_expected_entity_recall_is_deterministic() -> None:
    case = _case()

    assert _evaluate(case, _run(case.question)).cases[0].expected_entity_recall is True
    assert (
        _evaluate(case, _run(case.question, answer="A team owns it.")).cases[0].expected_entity_recall
        is False
    )


def test_grounded_and_ungrounded_runs_are_distinguished() -> None:
    case = _case()
    grounded = _evaluate(case, _run(case.question)).cases[0]
    ungrounded = _evaluate(
        case,
        AgentRun(question=case.question, final_answer="Payments owns it.", tool_calls=[]),
    ).cases[0]

    assert grounded.grounded is True
    assert ungrounded.grounded is False


def test_valid_and_invalid_no_result_handling() -> None:
    case = _case(
        id="none-1",
        question="Who owns Unknown API?",
        expected_argument="Unknown API",
        expected_entities=[],
        expect_no_result=True,
    )
    valid = _evaluate(
        case,
        _run(
            case.question,
            answer="The graph contains no matching result.",
            argument="Unknown API",
            result_count=0,
        ),
    ).cases[0]
    invalid = _evaluate(
        case,
        _run(
            case.question,
            answer="I do not know.",
            argument="Unknown API",
            result_count=0,
        ),
    ).cases[0]

    assert valid.no_result_correct is True
    assert invalid.no_result_correct is False


def test_errors_are_counted() -> None:
    case = _case()

    summary = _evaluate(case, ValueError("LLM unavailable"))

    assert summary.error_rate == 1.0
    assert summary.cases[0].error == "LLM unavailable"


def test_latency_percentiles_use_linear_interpolation() -> None:
    assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50) == 3.0
    assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 95) == 4.8


def test_benchmark_dataset_is_valid() -> None:
    cases = load_eval_cases(Path("data/agent_eval_cases.json"))

    assert len(cases) == 20
    assert {case.expected_tool for case in cases} == {
        "owners_for_service",
        "repositories_for_service",
        "services_affected_by_incident",
        "teams_for_person",
    }
    assert any(case.expect_no_result for case in cases)


def test_benchmark_dataset_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(
        '[{"id":"same","question":"q","expected_tool":"owners_for_service",'
        '"expected_argument":"x","expected_entities":[],"expect_no_result":true},'
        '{"id":"same","question":"q2","expected_tool":"owners_for_service",'
        '"expected_argument":"y","expected_entities":[],"expect_no_result":true}]',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unique"):
        load_eval_cases(path)


def test_no_result_case_validation_rejects_expected_entities() -> None:
    with pytest.raises(ValidationError, match="no-result"):
        _case(expected_entities=["Payments"], expect_no_result=True)
