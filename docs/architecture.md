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
- **Retrieval:** **future work.** It will locate useful graph information for a
  request.
- **Agent:** **future work.** It will use retrieved information to support a
  task.
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
