# Planned Architecture

This project grows in small, understandable steps. Ontology validation and two
domain-level representations now exist: an in-memory `OntologyGraph` and a
Neo4j persistence adapter.

```text
Data
  → Ontology validation
  → Knowledge Graph
  → Retrieval
  → Agent
  → API / MCP
```

## Component plan

- **Data:** source information supplied to the application.
- **Ontology validation:** Pydantic domain models validate ontology objects and
  relation domain/range combinations.
- **Knowledge Graph:** `OntologyGraph` provides a small in-memory domain
  container. `Neo4jRepository` is the first persistence implementation and
  stores the same domain objects and relations in Neo4j.
- **Retrieval:** `Neo4jGraphRetrieval` provides four fixed, typed graph lookups.
- **Agent:** `GraphAgent` selects one of those typed lookups through LLM tool
  calling and returns only after an approved graph tool has executed.
- **API / MCP:** **future work.** It will expose the application to callers and
  compatible tools.

The domain layer should remain independent from storage, network, and other
infrastructure choices.

## Domain and infrastructure separation

The `ontology` package owns object types, relation rules, and the in-memory
graph. It has no Neo4j dependency. The `infrastructure` package translates
those validated domain models to and from parameterized Cypher queries.

Neo4j connection settings come from `NEO4J_URI`, `NEO4J_USERNAME`,
`NEO4J_PASSWORD`, and `NEO4J_DATABASE`. Credentials must not be committed.

## Run the Neo4j smoke test

The smoke test writes four idempotent demo objects and three relations. It does
not delete or reset anything in Neo4j. Use a development database, not a shared
or production database. The Neo4j user needs permission to create the
object-ID constraint and to read and write graph data.

1. Install the project dependencies:

   ```powershell
   python -m pip install -e ".[dev]"
   ```

2. Set the connection variables in the same PowerShell window. Start from the
   safe placeholders in `.env.example`; the project does not load `.env` files
   automatically.

   ```powershell
   $env:NEO4J_URI = "neo4j://localhost:7687"
   $env:NEO4J_USERNAME = "neo4j"
   $env:NEO4J_PASSWORD = "replace-with-your-password"
   $env:NEO4J_DATABASE = "neo4j"
   ```

3. Run the smoke test from the repository root:

   ```powershell
   python scripts/neo4j_smoke.py
   ```

   A successful run reports that four objects, three relations, and the
   persisted `Payment API` were verified. Re-running it does not create
   duplicate demo nodes or identical relations.

## Run the optional live integration test

The normal test suite never requires Neo4j. To run the live test after setting
the connection variables above, explicitly opt in:

```powershell
$env:RUN_NEO4J_INTEGRATION = "1"
python -m pytest tests/test_neo4j_integration.py
```

This test writes two idempotent records with `integration-` IDs and one
relation. It does not remove them.

## Run the live graph-agent evaluation

The evaluation sends the checked-in questions to the configured LLM and reads
the existing Neo4j graph, so it may consume provider usage. It does not seed,
mutate, reset, or prepare graph data. Before running it, prepare the graph
separately so it contains the benchmark's expected sample facts for `Payments`,
`Payment API`, `payment-service`, `INC-204`, and `Alice`. Set `LLM_API_KEY`,
`LLM_BASE_URL`, and `LLM_MODEL`, then run:

```powershell
python scripts/evaluate_agent.py
```

It prints aggregate metrics and writes all per-case traces to
`artifacts/agent_eval_results.json`. No-result accuracy uses a deliberately
small set of English and Chinese phrases, so it can undercount correct but
unrecognized paraphrases; it is not an LLM-based quality judgment.
