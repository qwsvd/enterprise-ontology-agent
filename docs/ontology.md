# Planned Ontology

This document defines the intended ontology vocabulary. It is documentation
only: no Pydantic models or validation rules have been implemented yet.

## Object types

- `Person`
- `Team`
- `Service`
- `Repository`
- `Incident`

## Relations

- `Person MEMBER_OF Team`
- `Team OWNS Service`
- `Repository IMPLEMENTS Service`
- `Incident AFFECTS Service`

Future work can define attributes, identifiers, validation rules, and lifecycle
semantics for these types and relations.
