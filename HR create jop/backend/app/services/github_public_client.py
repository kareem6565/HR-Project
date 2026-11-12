from __future__ import annotations

import base64
import re
from datetime import UTC, datetime
from urllib.parse import unquote, urlsplit

import httpx

GITHUB_API = "https://api.github.com"
MAX_REPOSITORIES = 3
MAX_RESPONSE_BYTES = 512 * 1024
MAX_README_CHARS = 4_000
MAX_CONFIG_CHARS = 2_000
_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_CONFIG_FILES = (
    "pyproject.toml",
    "package.json",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
)


class GitHubFetchError(Exception):
    def __init__(self, code: str, retry_after_seconds: int | None = None):
        self.code = code
        self.retry_after_seconds = retry_after_seconds
        super().__init__(code)


def normalize_github_url(value: str) -> str:
    """Accept only a canonical public GitHub user or repository URL."""
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError("Enter a valid GitHub profile or repository URL.")
    parsed = urlsplit(value.strip())
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("Only standard GitHub links are supported.") from error
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != "github.com"
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Only https://github.com profile or repository links are supported.")
    parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
    if len(parts) not in (1, 2) or any(not _SEGMENT.fullmatch(part) for part in parts):
        raise ValueError("Use a GitHub profile URL or a public repository URL.")
    if len(parts) == 2 and parts[1].endswith(".git"):
        parts[1] = parts[1][:-4]
    if any(not _SEGMENT.fullmatch(part) for part in parts):
        raise ValueError("Use a GitHub profile URL or a public repository URL.")
    return "https://github.com/" + "/".join(parts)


class GitHubPublicClient:
    """Bounded, anonymous requests to GitHub's public REST API only."""

    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            timeout=httpx.Timeout(8.0, connect=4.0),
            follow_redirects=False,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "HERA-Public-Evidence-Review",
            },
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GitHubPublicClient:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def collect(self, repository_urls: list[str]) -> list[dict]:
        repos: list[tuple[str, str, str | None]] = []
        for value in repository_urls:
            normalized = normalize_github_url(value)
            path = urlsplit(normalized).path.strip("/").split("/")
            if len(path) == 2:
                repos.append((path[0], path[1], None))
            else:
                username = path[0]
                listing = self._get_json(
                    f"{GITHUB_API}/users/{username}/repos?type=owner&sort=updated&direction=desc&per_page={MAX_REPOSITORIES}&page=1"
                )
                if not isinstance(listing, list):
                    raise GitHubFetchError("INVALID_RESPONSE")
                repos.extend(
                    (item.get("owner", {}).get("login", username), item.get("name", ""), username)
                    for item in listing[:MAX_REPOSITORIES]
                    if isinstance(item, dict) and item.get("name")
                )
            if len(repos) >= MAX_REPOSITORIES:
                break

        observations: list[dict] = []
        seen: set[str] = set()
        for owner, name, profile_user in repos[:MAX_REPOSITORIES]:
            key = f"{owner}/{name}".casefold()
            if key in seen:
                continue
            seen.add(key)
            base = f"{GITHUB_API}/repos/{owner}/{name}"
            repo = self._get_json(base)
            if not isinstance(repo, dict) or repo.get("private") is True:
                continue
            html_url = repo.get("html_url")
            if not isinstance(html_url, str) or not html_url.startswith("https://github.com/"):
                continue
            source = f"https://github.com/{owner}/{name}"
            self._add(
                observations,
                "repository",
                source,
                {
                    "name": str(repo.get("full_name") or f"{owner}/{name}")[:200],
                    "description": str(repo.get("description") or "")[:1000],
                    "primary_language": str(repo.get("language") or "")[:80],
                    "updated_at": str(repo.get("updated_at") or "")[:40],
                    "fork": bool(repo.get("fork")),
                },
                "Repository metadata describes a project, not necessarily the candidate's work.",
            )

            languages = self._get_json(f"{base}/languages")
            if isinstance(languages, dict):
                self._add(
                    observations,
                    "languages",
                    source,
                    languages,
                    "Language statistics describe repository contents, not candidate proficiency.",
                )

            readme = self._optional_json(f"{base}/readme")
            if isinstance(readme, dict) and readme.get("encoding") == "base64":
                content = readme.get("content", "")
                if isinstance(content, str) and len(content) <= MAX_RESPONSE_BYTES:
                    try:
                        text = base64.b64decode(content, validate=False).decode("utf-8", "replace")
                    except (ValueError, UnicodeError):
                        text = ""
                    if text.strip():
                        self._add(
                            observations,
                            "readme",
                            readme.get("html_url") or source,
                            {"text": text[:MAX_README_CHARS]},
                            "Project documentation is indirect evidence; "
                            "another person may have authored it.",
                        )

            directory = self._optional_json(f"{base}/contents")
            manifest = next(
                (
                    item
                    for item in directory
                    if isinstance(item, dict)
                    and item.get("name") in _CONFIG_FILES
                    and item.get("type") == "file"
                )
                if isinstance(directory, list)
                else None
            )
            if manifest:
                file_data = self._optional_json(f"{base}/contents/{manifest['name']}")
                encoded = file_data.get("content", "") if isinstance(file_data, dict) else ""
                if (
                    isinstance(encoded, str)
                    and file_data.get("encoding") == "base64"
                    and len(encoded) <= MAX_RESPONSE_BYTES
                ):
                    try:
                        config = base64.b64decode(encoded, validate=False).decode(
                            "utf-8", "replace"
                        )
                    except (ValueError, UnicodeError):
                        config = ""
                    if config.strip():
                        self._add(
                            observations,
                            "project_configuration",
                            file_data.get("html_url") or source,
                            {"file": str(manifest["name"]), "text": config[:MAX_CONFIG_CHARS]},
                            "Configuration files show project dependencies, "
                            "not personal proficiency.",
                        )

            if profile_user:
                commits = self._get_json(f"{base}/commits?per_page=5&page=1")
                if isinstance(commits, list):
                    for commit in commits[:5]:
                        author = commit.get("author") if isinstance(commit, dict) else None
                        if (
                            isinstance(author, dict)
                            and str(author.get("login", "")).casefold() == profile_user.casefold()
                        ):
                            self._add(
                                observations,
                                "account_attributed_commit",
                                str(commit.get("html_url") or source),
                                {
                                    "author_login": profile_user,
                                    "message": str(commit.get("commit", {}).get("message", ""))[
                                        :300
                                    ],
                                },
                                "GitHub attributes this commit to the account; "
                                "attribution does not "
                                "prove identity or amount of work.",
                            )
        return observations

    def _get_json(self, url: str):
        try:
            with self._client.stream("GET", url) as response:
                if response.status_code == 404:
                    raise GitHubFetchError("NOT_FOUND")
                if response.status_code in (403, 429):
                    retry_after = response.headers.get("Retry-After")
                    reset_at = response.headers.get("X-RateLimit-Reset")
                    seconds = None
                    if retry_after and retry_after.isdigit():
                        seconds = int(retry_after)
                    elif reset_at and reset_at.isdigit():
                        seconds = max(1, int(reset_at) - int(datetime.now(UTC).timestamp()))
                    raise GitHubFetchError("RATE_LIMITED", min(seconds, 3600) if seconds else 3600)
                if response.status_code >= 500:
                    raise GitHubFetchError("GITHUB_UNAVAILABLE")
                if response.status_code >= 400:
                    raise GitHubFetchError("GITHUB_REQUEST_REJECTED")
                chunks = bytearray()
                for chunk in response.iter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE_BYTES:
                        raise GitHubFetchError("RESPONSE_TOO_LARGE")
            import json

            return json.loads(chunks)
        except httpx.TimeoutException as error:
            raise GitHubFetchError("TIMEOUT") from error
        except httpx.HTTPError as error:
            raise GitHubFetchError("NETWORK_ERROR") from error
        except ValueError as error:
            if isinstance(error, GitHubFetchError):
                raise
            raise GitHubFetchError("INVALID_RESPONSE") from error

    @staticmethod
    def _add(
        target: list[dict], kind: str, source_url: str, content: dict, limitation: str
    ) -> None:
        target.append(
            {
                "evidence_id": f"gh-{len(target) + 1}",
                "kind": kind,
                "source_url": source_url,
                "content": content,
                "limitation": limitation,
            }
        )

    def _optional_json(self, url: str):
        try:
            return self._get_json(url)
        except GitHubFetchError as error:
            if error.code == "NOT_FOUND":
                return None
            raise
