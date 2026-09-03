"""Tests for GitHub repository ingestion without network access."""

import json
from typing import Any

import pytest

from enterprise_ontology_agent.infrastructure import ingest_github_repository
from enterprise_ontology_agent.ontology import ObjectType


class FakeRepository:
    def __init__(self) -> None:
        self.objects = []

    def save_object(self, ontology_object: object) -> None:
        self.objects.append(ontology_object)


class FakeResponse:
    def __init__(self, data: Any) -> None:
        self._data = json.dumps(data).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, *args: object) -> bytes:
        return self._data


class FakeUrlOpen:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = responses
        self.requests = []

    def __call__(self, request: object, timeout: int) -> FakeResponse:
        self.requests.append(request)
        return FakeResponse(self._responses.pop(0))


@pytest.mark.parametrize(
    ("token", "authorization"),
    [(None, None), ("test-token", "Bearer test-token")],
)
def test_ingests_repository_metadata_and_persists_object(
    token: str | None,
    authorization: str | None,
) -> None:
    urlopen_func = FakeUrlOpen(
        [
            {
                "id": 123,
                "full_name": "octo/example",
                "html_url": "https://github.com/octo/example",
            },
            [{"number": 1}, {"number": 2, "pull_request": {}}],
            [{"number": 3}],
        ]
    )
    repository = FakeRepository()

    result = ingest_github_repository(
        "octo/example",
        repository,  # type: ignore[arg-type]
        token=token,
        urlopen_func=urlopen_func,
    )

    assert result.issue_count == 1
    assert result.pull_request_count == 1
    assert result.ontology_object.id == "github-repository-123"
    assert result.ontology_object.name == "octo/example"
    assert result.ontology_object.object_type is ObjectType.REPOSITORY
    assert result.ontology_object.source_url == "https://github.com/octo/example"
    assert result.ontology_object.source_type == "github_repository"
    assert result.ontology_object.external_id == "123"
    assert repository.objects == [result.ontology_object]
    assert urlopen_func.requests[0].full_url == "https://api.github.com/repos/octo/example"
    assert urlopen_func.requests[1].full_url.endswith("/issues?state=all&sort=updated&direction=desc&per_page=10")
    assert urlopen_func.requests[2].full_url.endswith("/pulls?state=all&sort=updated&direction=desc&per_page=10")
    assert urlopen_func.requests[0].get_header("Authorization") == authorization


@pytest.mark.parametrize("repository_name", ["example", "octo/", "/example", "a/b/c"])
def test_rejects_invalid_repository_name_without_network_access(
    repository_name: str,
) -> None:
    urlopen_func = FakeUrlOpen([])

    with pytest.raises(ValueError, match="owner/repo"):
        ingest_github_repository(
            repository_name,
            FakeRepository(),  # type: ignore[arg-type]
            urlopen_func=urlopen_func,
        )

    assert urlopen_func.requests == []
