# Current Architecture

The project separates ontology rules from network and storage adapters. Domain
models are valid without Neo4j, an LLM provider, GitHub, or MCP.

```text
Data sources
  → ingestion or LLM extraction
  → Pydantic ontology validation
  → Neo4jRepository
  → Neo4j
  → fixed Neo4jGraphRetrieval operations
  → GraphAgent or read-only MCP tools
```

## Component boundaries

- `ontology` defines `ObjectType`, `RelationType`, `OntologyObject`,
  `OntologyRelation`, and the in-memory `OntologyGraph`. It contains all
  relation domain/range rules and has no infrastructure dependency.
- `infrastructure` contains JSON, GitHub, and LLM ingestion, Neo4j persistence,
  typed retrieval, the bounded graph agent, and evaluation logic.
- `Neo4jRepository` serializes validated domain objects and relations. It keeps
  object IDs unique, prevents object-type changes, avoids duplicate identical
  relations, and preserves stored provenance when an update supplies `None`.
- `Neo4jGraphRetrieval` runs four fixed, parameterized, read-only Cypher queries
  and reconstructs `OntologyObject` values, including provenance.
- `GraphAgent` lets an OpenAI-compatible LLM select only those four operations.
  Tool names and arguments are validated, execution is limited to three tool
  rounds, and a final answer requires at least one completed graph tool.
- The MCP v2 layer exposes the same four retrieval operations over stdio. It
  shares one retrieval connection for the server lifespan and does not call an
  LLM or expose arbitrary Cypher.

There is no HTTP application API. API delivery remains future work.

## Configuration

Neo4j connections use `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and
`NEO4J_DATABASE`. LLM-backed extraction, agent, and evaluation paths use
`LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL`. GitHub ingestion can optionally
use `GITHUB_TOKEN`; public repositories can be read without it subject to API
rate limits.

The project reads these values from the process environment and does not load a
`.env` file automatically.

## Neo4j smoke test

The smoke test writes four idempotent objects and three relations. It does not
delete or reset data. Use a development database whose user can create the
object-ID constraint and read and write graph data.

```powershell
python scripts/neo4j_smoke.py
```

It saves and reads `Payments`, `Payment API`, `payment-service`, and `INC-204`,
checks the three direct neighbors of `Payment API`, closes the connection,
reconnects, and verifies persistence. Re-running it does not create duplicate
nodes or identical relations.

## Optional live Neo4j integration test

The normal suite does not require Neo4j. Explicitly opt in after configuring a
development database:

```powershell
$env:RUN_NEO4J_INTEGRATION = "1"
python -m pytest tests/test_neo4j_integration.py
```

The test writes two records with `integration-` IDs and one relation. It does
not remove them.

## Graph-agent evaluation

Evaluation reads the existing Neo4j graph and calls the configured LLM. It does
not seed, mutate, reset, or otherwise prepare graph data. Data preparation is a
separate step; the expected sample facts must already exist.

```powershell
python scripts/evaluate_agent.py
```

The command prints aggregate metrics and writes complete per-case traces to
`artifacts/agent_eval_results.json`. See [evaluation.md](evaluation.md) for the
methodology and limitations.

## MCP data flow

```text
MCP Host
  ↓
MCP Client
  ↓ stdio
Enterprise Ontology MCP Server
  ↓
typed Neo4jGraphRetrieval
  ↓
Neo4j
```

Start the protocol server without ordinary stdout output:

```powershell
python scripts/mcp_server.py
```

Inspect the server during development with the official MCP CLI and Inspector:

```powershell
mcp dev scripts/mcp_server.py
```

Only four deterministic read-only tools are exposed. There are no MCP resources,
prompts, sampling, LLM calls, authentication, HTTP transport, or arbitrary
Cypher execution.
