from __future__ import annotations

import base64
import json

import httpx
import pytest

from app.services.github_public_client import (
    GitHubFetchError,
    GitHubPublicClient,
    normalize_github_url,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://github.com/octocat", "https://github.com/octocat"),
        ("https://github.com/octocat/Hello-World.git", "https://github.com/octocat/Hello-World"),
    ],
)
def test_normalizes_only_supported_public_github_urls(value: str, expected: str) -> None:
    assert normalize_github_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "http://github.com/octocat",
        "https://github.com.evil.test/octocat",
        "https://user:pass@github.com/octocat",
        "https://github.com:444/octocat",
        "https://github.com/octocat?redirect=example.test",
        "https://github.com/octocat%2Frepo",
        "https://example.test/octocat/repo",
    ],
)
def test_rejects_noncanonical_or_unsafe_github_urls(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_github_url(value)


def test_collects_bounded_public_evidence_from_mocked_github_api() -> None:
    manifest = base64.b64encode(b"[project]\nname='demo'\n").decode()
    readme = base64.b64encode(b"# Demo\nBuilt with Python and FastAPI.\n").decode()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/users/alex/repos":
            return httpx.Response(200, json=[{"name": "demo", "owner": {"login": "alex"}}])
        if path == "/repos/alex/demo":
            return httpx.Response(
                200,
                json={
                    "private": False,
                    "full_name": "alex/demo",
                    "html_url": "https://github.com/alex/demo",
                    "description": "A demo project",
                    "language": "Python",
                    "updated_at": "2026-11-01T00:00:00Z",
                    "fork": False,
                },
            )
        if path == "/repos/alex/demo/languages":
            return httpx.Response(200, json={"Python": 1000})
        if path == "/repos/alex/demo/readme":
            return httpx.Response(
                200,
                json={
                    "encoding": "base64",
                    "content": readme,
                    "html_url": "https://github.com/alex/demo/blob/main/README.md",
                },
            )
        if path == "/repos/alex/demo/contents":
            return httpx.Response(200, json=[{"name": "pyproject.toml", "type": "file"}])
        if path == "/repos/alex/demo/contents/pyproject.toml":
            return httpx.Response(
                200,
                json={
                    "encoding": "base64",
                    "content": manifest,
                    "html_url": "https://github.com/alex/demo/blob/main/pyproject.toml",
                },
            )
        if path == "/repos/alex/demo/commits":
            return httpx.Response(
                200,
                json=[
                    {
                        "author": {"login": "alex"},
                        "html_url": "https://github.com/alex/demo/commit/abc",
                        "commit": {"message": "Add demo"},
                    }
                ],
            )
        raise AssertionError(f"Unexpected GitHub API path: {path}")

    with GitHubPublicClient(transport=httpx.MockTransport(handler)) as client:
        observations = client.collect(["https://github.com/alex"])

    kinds = {item["kind"] for item in observations}
    assert kinds == {
        "repository",
        "languages",
        "readme",
        "project_configuration",
        "account_attributed_commit",
    }
    assert all(item["evidence_id"] for item in observations)
    assert any("does not prove" in item["limitation"] for item in observations)
    assert all(item["source_url"].startswith("https://github.com/") for item in observations)


def test_rate_limit_is_classified_and_honors_retry_headers() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "42"})

    with GitHubPublicClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GitHubFetchError) as error:
            client.collect(["https://github.com/octocat/repo"])
    assert error.value.code == "RATE_LIMITED"
    assert error.value.retry_after_seconds == 42


def test_oversized_response_is_rejected() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({"large": "x" * 600_000}))

    with GitHubPublicClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(GitHubFetchError, match="RESPONSE_TOO_LARGE"):
            client.collect(["https://github.com/octocat/repo"])
