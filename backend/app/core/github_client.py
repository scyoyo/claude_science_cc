"""
GitHub API client for pushing meeting artifacts to a repository.

Uses REST API: create repo (optional), then Contents API to create/update files.
Token is used only for the request; not stored or logged.
"""

import base64
import logging
from typing import List

import httpx

GITHUB_API = "https://api.github.com"
LOG = logging.getLogger(__name__)


class GitHubPushError(Exception):
    """Raised when a GitHub API call fails with a message for the user."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _headers(token: str) -> dict:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_current_user(token: str) -> str:
    """Return the authenticated user's login. Raises GitHubPushError on failure."""
    with httpx.Client(timeout=15.0) as client:
        r = client.get(f"{GITHUB_API}/user", headers=_headers(token))
        if r.status_code != 200:
            try:
                detail = r.json().get("message", r.text) or f"HTTP {r.status_code}"
            except Exception:
                detail = r.text or f"HTTP {r.status_code}"
            raise GitHubPushError(detail, r.status_code)
        return r.json().get("login", "")


def ensure_repo(token: str, repo_owner: str, repo_name: str, create_if_missing: bool) -> None:
    """Ensure the repository exists. If create_if_missing and repo does not exist, create it."""
    with httpx.Client(timeout=15.0) as client:
        r = client.get(
            f"{GITHUB_API}/repos/{repo_owner}/{repo_name}",
            headers=_headers(token),
        )
        if r.status_code == 200:
            return
        if r.status_code != 404:
            try:
                detail = r.json().get("message", r.text) or r.text
            except Exception:
                detail = r.text or f"HTTP {r.status_code}"
            raise GitHubPushError(detail, r.status_code)
        if not create_if_missing:
            raise GitHubPushError(
                f"Repository {repo_owner}/{repo_name} not found. Enable 'Create repo if missing' to create it.",
                404,
            )
        # Create repo: user repo vs org repo
        login = get_current_user(token)
        if login == repo_owner:
            create_r = client.post(
                f"{GITHUB_API}/user/repos",
                headers=_headers(token),
                json={"name": repo_name, "private": False},
            )
        else:
            create_r = client.post(
                f"{GITHUB_API}/orgs/{repo_owner}/repos",
                headers=_headers(token),
                json={"name": repo_name, "private": False},
            )
        if create_r.status_code not in (200, 201):
            try:
                detail = create_r.json().get("message", create_r.text) or create_r.text
            except Exception:
                detail = create_r.text or f"HTTP {create_r.status_code}"
            raise GitHubPushError(detail, create_r.status_code)


def push_files(
    token: str,
    repo_owner: str,
    repo_name: str,
    files: List[dict],
    commit_message: str = "Update from Virtual Lab",
) -> None:
    """Create or update each file in the repo. Each item in files must have 'path' and 'content' (str)."""
    with httpx.Client(timeout=30.0) as client:
        for item in files:
            path = item.get("path", "").strip()
            content = item.get("content", "")
            if not path:
                continue
            content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            sha = None
            get_r = client.get(
                f"{GITHUB_API}/repos/{repo_owner}/{repo_name}/contents/{path}",
                headers=_headers(token),
            )
            if get_r.status_code == 200:
                try:
                    sha = get_r.json().get("sha")
                except Exception:
                    pass
            elif get_r.status_code != 404:
                try:
                    detail = get_r.json().get("message", get_r.text) or get_r.text
                except Exception:
                    detail = get_r.text or f"HTTP {get_r.status_code}"
                raise GitHubPushError(detail, get_r.status_code)

            body = {"message": commit_message, "content": content_b64}
            if sha:
                body["sha"] = sha
            put_r = client.put(
                f"{GITHUB_API}/repos/{repo_owner}/{repo_name}/contents/{path}",
                headers=_headers(token),
                json=body,
            )
            if put_r.status_code not in (200, 201):
                try:
                    detail = put_r.json().get("message", put_r.text) or put_r.text
                except Exception:
                    detail = put_r.text or f"HTTP {put_r.status_code}"
                raise GitHubPushError(detail, put_r.status_code)
