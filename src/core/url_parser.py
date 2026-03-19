"""Parse GitHub URLs into structured components."""

import re
import hashlib
from dataclasses import dataclass


@dataclass
class RepoTarget:
    org: str
    repo: str
    branch: str
    scope_path: str  # "" for full repo
    clone_url: str
    url: str  # original URL

    @property
    def cache_key(self) -> str:
        """Unique cache key for this repo+branch+scope combination."""
        raw = f"{self.org}_{self.repo}_{self.branch}_{self.scope_path}"
        scope_hash = hashlib.md5(raw.encode()).hexdigest()[:12]
        return f"{self.org}_{self.repo}_{scope_hash}"

    @property
    def display_name(self) -> str:
        if self.scope_path:
            return f"{self.org}/{self.repo} → {self.scope_path}"
        return f"{self.org}/{self.repo}"


def parse_github_url(url: str) -> RepoTarget:
    """
    Parse a GitHub URL into its components.

    Supported formats:
      https://github.com/org/repo
      https://github.com/org/repo/tree/branch
      https://github.com/org/repo/tree/branch/path/to/dir
    """
    url = url.rstrip("/")

    # Pattern: https://github.com/ORG/REPO/tree/BRANCH/PATH...
    match = re.match(
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/tree/([^/]+)(?:/(.+))?)?$",
        url,
    )
    if not match:
        raise ValueError(
            f"Invalid GitHub URL: {url}\n"
            "Expected format: https://github.com/org/repo[/tree/branch[/path]]"
        )

    org = match.group(1)
    repo = match.group(2)
    branch = match.group(3) or "main"
    scope_path = match.group(4) or ""

    clone_url = f"https://github.com/{org}/{repo}.git"

    return RepoTarget(
        org=org,
        repo=repo,
        branch=branch,
        scope_path=scope_path,
        clone_url=clone_url,
        url=url,
    )
