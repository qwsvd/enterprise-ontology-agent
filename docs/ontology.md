# Planned Ontology

This document defines the current ontology vocabulary. The object and relation
types are implemented as string enums, and Pydantic models validate objects and
relation domain/range combinations.

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

`OntologyObject` contains an `id`, `name`, and `object_type`.
It may also contain optional provenance fields: `source_url`, `source_type`,
and `external_id`.
`OntologyRelation` contains source and target IDs and types plus a relation
type. IDs and object names cannot be blank, and only the relation combinations
listed above are accepted.

Future work can define additional attributes and lifecycle semantics. Graph
storage and other infrastructure remain outside the ontology domain model.
