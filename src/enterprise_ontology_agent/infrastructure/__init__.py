"""Infrastructure adapters for the application."""

from enterprise_ontology_agent.infrastructure.json_ingestion import ingest_json
from enterprise_ontology_agent.infrastructure.neo4j import Neo4jRepository

__all__ = ["Neo4jRepository", "ingest_json"]
