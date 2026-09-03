"""Deterministic evaluation helpers for the typed graph agent.

No-result completion detection is intentionally limited to a small set of
English and Chinese phrases. It does not judge paraphrases or factual quality.
"""

import json
import math
from collections.abc import Callable, Sequence
from pathlib import Path
from time import perf_counter
from typing import Literal, Protocol

from pydantic import BaseModel, field_validator, model_validator

from enterprise_ontology_agent.infrastructure.graph_agent import AgentRun


_NO_RESULT_PHRASES = (
    "no matching result",
    "no matching graph result",
    "no results found",
    "没有匹配",
    "未找到",
    "无匹配",
)


class EvalCase(BaseModel):
    """One expected tool-calling graph-agent evaluation case."""

    id: str
    question: str
    expected_tool: Literal[
        "owners_for_service",
        "repositories_for_service",
        "services_affected_by_incident",
        "teams_for_person",
    ]
    expected_argument: str
    expected_entities: list[str]
    expect_no_result: bool

    @field_validator("id", "question", "expected_argument")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("expected_entities")
    @classmethod
    def entity_names_must_not_be_blank(cls, value: list[str]) -> list[str]:
        if any(not isinstance(name, str) or not name.strip() for name in value):
            raise ValueError("must contain only nonblank entity names")
        return value

    @model_validator(mode="after")
    def no_result_cases_must_not_expect_entities(self) -> "EvalCase":
        if self.expect_no_result and self.expected_entities:
            raise ValueError("no-result cases must not include expected entities")
        return self


class EvalCaseResult(BaseModel):
    """Metrics and raw trace details from evaluating one case."""

    case_id: str
    question: str
    expected_tool: str
    expected_argument: str
    final_answer: str | None = None
    executed_tool: str | None = None
    executed_argument: str | None = None
    result_count: int | None = None
    result_ids: list[str] = []
    result_names: list[str] = []
    tool_selection_correct: bool = False
    argument_correct: bool = False
    expected_entity_recall: bool | None = None
    grounded: bool = False
    no_result_correct: bool | None = None
    error: str | None = None
    latency_seconds: float


class EvalSummary(BaseModel):
    """Per-case results and deterministic aggregate metrics."""

    cases: list[EvalCaseResult]
    tool_selection_accuracy: float
    argument_accuracy: float
    expected_entity_recall: float
    grounded_completion_rate: float
    no_result_accuracy: float
    error_rate: float
    latency_mean_seconds: float
    latency_p50_seconds: float
    latency_p95_seconds: float


class AgentRunner(Protocol):
    """The small part of GraphAgent required by the evaluator."""

    def run(self, question: str) -> AgentRun:
        """Return one traced agent run."""


def load_eval_cases(path: Path) -> list[EvalCase]:
    """Load and validate the checked-in evaluation cases."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Evaluation cases contain invalid JSON: {error.msg}") from error
    if not isinstance(data, list):
        raise ValueError("Evaluation cases must be a JSON list")

    cases = [EvalCase.model_validate(item) for item in data]
    identifiers = [case.id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Evaluation case IDs must be unique")
    if not cases:
        raise ValueError("Evaluation cases must not be empty")
    return cases


def evaluate_cases(
    cases: Sequence[EvalCase],
    agent: AgentRunner,
    clock: Callable[[], float] = perf_counter,
) -> EvalSummary:
    """Run cases and calculate deterministic trace-based evaluation metrics."""
    results: list[EvalCaseResult] = []
    for case in cases:
        started_at = clock()
        try:
            run = agent.run(case.question)
        except Exception as error:  # Record agent failures as benchmark results.
            results.append(
                _error_result(case, str(error), clock() - started_at)
            )
            continue
        results.append(_result_for_run(case, run, clock() - started_at))
    return _summary(results)


def _result_for_run(
    case: EvalCase,
    run: AgentRun,
    latency_seconds: float,
) -> EvalCaseResult:
    tool_call = run.tool_calls[0] if run.tool_calls else None
    final_answer = run.final_answer
    entity_recall = None
    if case.expected_entities:
        answer = final_answer.casefold()
        entity_recall = all(entity.casefold() in answer for entity in case.expected_entities)

    no_result_correct = None
    if case.expect_no_result:
        no_result_correct = (
            tool_call is not None
            and tool_call.result_count == 0
            and _indicates_no_result(final_answer)
        )

    return EvalCaseResult(
        case_id=case.id,
        question=case.question,
        expected_tool=case.expected_tool,
        expected_argument=case.expected_argument,
        final_answer=final_answer,
        executed_tool=tool_call.tool_name if tool_call else None,
        executed_argument=tool_call.argument if tool_call else None,
        result_count=tool_call.result_count if tool_call else None,
        result_ids=tool_call.result_ids if tool_call else [],
        result_names=tool_call.result_names if tool_call else [],
        tool_selection_correct=tool_call is not None and tool_call.tool_name == case.expected_tool,
        argument_correct=tool_call is not None and tool_call.argument == case.expected_argument,
        expected_entity_recall=entity_recall,
        grounded=bool(run.tool_calls),
        no_result_correct=no_result_correct,
        latency_seconds=latency_seconds,
    )


def _error_result(case: EvalCase, error: str, latency_seconds: float) -> EvalCaseResult:
    return EvalCaseResult(
        case_id=case.id,
        question=case.question,
        expected_tool=case.expected_tool,
        expected_argument=case.expected_argument,
        expected_entity_recall=False if case.expected_entities else None,
        no_result_correct=False if case.expect_no_result else None,
        error=error,
        latency_seconds=latency_seconds,
    )


def _summary(results: list[EvalCaseResult]) -> EvalSummary:
    latencies = [result.latency_seconds for result in results]
    return EvalSummary(
        cases=results,
        tool_selection_accuracy=_rate(
            [result.tool_selection_correct for result in results]
        ),
        argument_accuracy=_rate([result.argument_correct for result in results]),
        expected_entity_recall=_rate(
            [
                result.expected_entity_recall
                for result in results
                if result.expected_entity_recall is not None
            ]
        ),
        grounded_completion_rate=_rate([result.grounded for result in results]),
        no_result_accuracy=_rate(
            [
                result.no_result_correct
                for result in results
                if result.no_result_correct is not None
            ]
        ),
        error_rate=_rate([result.error is not None for result in results]),
        latency_mean_seconds=sum(latencies) / len(latencies),
        latency_p50_seconds=_percentile(latencies, 50),
        latency_p95_seconds=_percentile(latencies, 95),
    )


def _rate(values: Sequence[bool]) -> float:
    return sum(values) / len(values) if values else 0.0


def _percentile(values: Sequence[float], percent: int) -> float:
    """Calculate a linear-interpolated percentile from a nonempty sequence."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _indicates_no_result(answer: str) -> bool:
    normalized = answer.casefold()
    return any(phrase in normalized for phrase in _NO_RESULT_PHRASES)
