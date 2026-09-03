"""Import public GitHub repository metadata into the ontology."""

import json
from dataclasses import dataclass
from typing import Any, Callable
from urllib.request import Request, urlopen

from enterprise_ontology_agent.infrastructure.neo4j import Neo4jRepository
from enterprise_ontology_agent.ontology import ObjectType, OntologyObject


GITHUB_API_URL = "https://api.github.com"
_RECENT_ITEMS_QUERY = "state=all&sort=updated&direction=desc&per_page=10"


@dataclass(frozen=True)
class GitHubRepositoryImport:
    """Repository data imported from GitHub."""

    ontology_object: OntologyObject
    issue_count: int
    pull_request_count: int


def ingest_github_repository(
    repository_name: str,
    repository: Neo4jRepository,
    *,
    token: str | None = None,
    urlopen_func: Callable[..., Any] = urlopen,
) -> GitHubRepositoryImport:
    """Fetch and persist a GitHub repository as an ontology Repository object."""
    owner, name = _parse_repository_name(repository_name)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "enterprise-ontology-agent",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    metadata = _get_json(
        f"{GITHUB_API_URL}/repos/{owner}/{name}", headers, urlopen_func
    )
    issues = _get_json(
        f"{GITHUB_API_URL}/repos/{owner}/{name}/issues?{_RECENT_ITEMS_QUERY}",
        headers,
        urlopen_func,
    )
    pull_requests = _get_json(
        f"{GITHUB_API_URL}/repos/{owner}/{name}/pulls?{_RECENT_ITEMS_QUERY}",
        headers,
        urlopen_func,
    )

    ontology_object = OntologyObject(
        id=f"github-repository-{metadata['id']}",
        name=metadata["full_name"],
        object_type=ObjectType.REPOSITORY,
        source_url=metadata["html_url"],
        source_type="github_repository",
        external_id=str(metadata["id"]),
    )
    repository.save_object(ontology_object)

    issue_count = sum(
        1 for issue in issues if "pull_request" not in issue
    )
    return GitHubRepositoryImport(
        ontology_object=ontology_object,
        issue_count=issue_count,
        pull_request_count=len(pull_requests),
    )


def _parse_repository_name(repository_name: str) -> tuple[str, str]:
    parts = repository_name.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("Repository must use the 'owner/repo' format")
    return parts[0], parts[1]


def _get_json(
    url: str,
    headers: dict[str, str],
    urlopen_func: Callable[..., Any],
) -> Any:
    request = Request(url, headers=headers)
    with urlopen_func(request, timeout=10) as response:
        return json.load(response)
