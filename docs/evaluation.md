# Evaluation Methodology

The graph-agent evaluation uses 20 controlled cases from
`data/agent_eval_cases.json`. The cases cover all four typed retrieval tools,
direct and paraphrased English questions, direct and paraphrased Chinese
questions, and explicit no-result queries.

## Measurement

`GraphAgent.run()` records the tool name, exact argument, result count, result
IDs, and result names for every graph tool that actually executes. The evaluator
uses those traces and `time.perf_counter()` to produce per-case records and these
aggregate metrics:

- **Tool selection accuracy:** the first executed tool matches `expected_tool`.
- **Argument accuracy:** the first executed argument exactly matches
  `expected_argument`.
- **Expected entity recall:** every expected entity name occurs in the final
  answer using case-insensitive text matching; this is calculated on positive
  cases only.
- **Grounded completion rate:** at least one approved graph tool executed before
  the final answer.
- **No-result accuracy:** the graph returned an empty result and the answer used
  one of a conservative set of English or Chinese no-result phrases.
- **Error rate:** the proportion of cases that raised an exception.
- **Latency:** total wall-clock mean, p50, and p95 using linear-interpolated
  percentiles.

No semantic similarity model or LLM judge is used. Failures remain visible in
the per-case output, and cases are not retried automatically.

## Reproduction

Prepare Neo4j separately with the expected sample facts, configure the Neo4j and
LLM environment variables, and run:

```powershell
python scripts/evaluate_agent.py
```

The evaluator reads the existing graph without mutating it and writes results to
`artifacts/agent_eval_results.json`. A live run may consume LLM API usage.

## Limitations

The dataset is a small controlled check of known entity names and four query
patterns. Expected-entity recall is literal text matching, and no-result
detection recognizes only a short phrase list. The measurements therefore do
not establish general language understanding, extraction correctness,
production reliability, or scalability.
