# Planned Architecture

This project will grow in small, understandable steps. The current repository
contains only a Python package scaffold; none of the components below are
implemented yet.

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
- **Ontology validation:** validates data against the planned ontology. This is
  planned work; no ontology models exist yet.
- **Knowledge Graph:** **future work.** It will represent validated entities and
  their relationships.
- **Retrieval:** **future work.** It will locate useful graph information for a
  request.
- **Agent:** **future work.** It will use retrieved information to support a
  task.
- **API / MCP:** **future work.** It will expose the application to callers and
  compatible tools.

The domain layer should remain independent from storage, network, and other
infrastructure choices.
