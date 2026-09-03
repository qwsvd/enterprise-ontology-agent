"""Core ontology objects and relations."""

from enum import Enum

from pydantic import BaseModel, field_validator, model_validator


class ObjectType(str, Enum):
    """Object types supported by the enterprise ontology."""

    PERSON = "Person"
    TEAM = "Team"
    SERVICE = "Service"
    REPOSITORY = "Repository"
    INCIDENT = "Incident"


class RelationType(str, Enum):
    """Relation types supported by the enterprise ontology."""

    MEMBER_OF = "MEMBER_OF"
    OWNS = "OWNS"
    IMPLEMENTS = "IMPLEMENTS"
    AFFECTS = "AFFECTS"


class OntologyObject(BaseModel):
    """A named object in the enterprise ontology."""

    id: str
    name: str
    object_type: ObjectType
    source_url: str | None = None
    source_type: str | None = None
    external_id: str | None = None

    @field_validator("id", "name")
    @classmethod
    def value_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("source_url", "source_type", "external_id")
    @classmethod
    def provenance_value_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value


class OntologyRelation(BaseModel):
    """A typed relation between two ontology objects."""

    source_id: str
    source_type: ObjectType
    relation_type: RelationType
    target_id: str
    target_type: ObjectType

    @field_validator("source_id", "target_id")
    @classmethod
    def id_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def relation_must_have_allowed_domain_and_range(self) -> "OntologyRelation":
        expected_types = _ALLOWED_RELATIONS[self.relation_type]
        actual_types = (self.source_type, self.target_type)
        if actual_types != expected_types:
            expected_source, expected_target = expected_types
            raise ValueError(
                f"Invalid relation: {self.source_type.value} "
                f"{self.relation_type.value} {self.target_type.value}. "
                f"Expected {expected_source.value} {self.relation_type.value} "
                f"{expected_target.value}."
            )
        return self


_ALLOWED_RELATIONS: dict[RelationType, tuple[ObjectType, ObjectType]] = {
    RelationType.MEMBER_OF: (ObjectType.PERSON, ObjectType.TEAM),
    RelationType.OWNS: (ObjectType.TEAM, ObjectType.SERVICE),
    RelationType.IMPLEMENTS: (ObjectType.REPOSITORY, ObjectType.SERVICE),
    RelationType.AFFECTS: (ObjectType.INCIDENT, ObjectType.SERVICE),
}
