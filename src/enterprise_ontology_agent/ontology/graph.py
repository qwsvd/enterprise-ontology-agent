"""In-memory container for ontology objects and relations."""

from enterprise_ontology_agent.ontology.models import (
    OntologyObject,
    OntologyRelation,
)


class OntologyGraph:
    """Store and connect ontology objects in memory."""

    def __init__(self) -> None:
        self._objects: dict[str, OntologyObject] = {}
        self._relations: list[OntologyRelation] = []

    def add_object(self, ontology_object: OntologyObject) -> None:
        """Add an object, rejecting an ID that is already present."""
        if ontology_object.id in self._objects:
            raise ValueError(f"Object with id '{ontology_object.id}' already exists")
        self._objects[ontology_object.id] = ontology_object

    def get_object(self, object_id: str) -> OntologyObject | None:
        """Return an object by ID, or None when it is not present."""
        return self._objects.get(object_id)

    def add_relation(self, relation: OntologyRelation) -> None:
        """Add a relation after checking its endpoints against stored objects."""
        source = self._objects.get(relation.source_id)
        if source is None:
            raise ValueError(f"Source object '{relation.source_id}' does not exist")

        target = self._objects.get(relation.target_id)
        if target is None:
            raise ValueError(f"Target object '{relation.target_id}' does not exist")

        if source.object_type is not relation.source_type:
            raise ValueError(
                f"Source type mismatch for '{relation.source_id}': stored object is "
                f"{source.object_type.value}, relation expects {relation.source_type.value}"
            )

        if target.object_type is not relation.target_type:
            raise ValueError(
                f"Target type mismatch for '{relation.target_id}': stored object is "
                f"{target.object_type.value}, relation expects {relation.target_type.value}"
            )

        self._relations.append(relation)

    def get_neighbors(self, object_id: str) -> list[OntologyObject]:
        """Return unique objects directly connected to an object."""
        neighbor_ids: list[str] = []

        for relation in self._relations:
            if relation.source_id == object_id:
                neighbor_id = relation.target_id
            elif relation.target_id == object_id:
                neighbor_id = relation.source_id
            else:
                continue

            if neighbor_id not in neighbor_ids:
                neighbor_ids.append(neighbor_id)

        return [self._objects[neighbor_id] for neighbor_id in neighbor_ids]
