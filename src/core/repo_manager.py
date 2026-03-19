"""Manage git clone, cache directory, and cleanup."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from rich.console import Console

from .url_parser import RepoTarget

console = Console()

DPAI_HOME = Path.home() / ".dpai_sds_gen"
CLONES_DIR = DPAI_HOME / "clones"
CACHE_DIR = DPAI_HOME / "cache"


def ensure_dirs():
    """Create dpai_sds_gen home directories if they don't exist."""
    CLONES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_dir(target: RepoTarget) -> Path:
    """Get the cache directory for a repo target."""
    return CACHE_DIR / target.cache_key


def get_clone_dir(target: RepoTarget) -> Path:
    """Get the clone directory for a repo target."""
    return CLONES_DIR / target.cache_key


def clone_repo(target: RepoTarget, token: Optional[str] = None) -> Path:
    """
    Clone the repo to a local temp directory.
    Uses shallow clone (--depth=1) for speed.
    Returns the path to the clone directory.
    """
    ensure_dirs()
    clone_dir = get_clone_dir(target)

    # If clone already exists (from a failed previous run), remove it
    if clone_dir.exists():
        shutil.rmtree(clone_dir)

    # Build clone URL with token for private repos
    clone_url = target.clone_url
    if token:
        clone_url = clone_url.replace(
            "https://github.com",
            f"https://{token}@github.com",
        )

    console.print(f"[blue]Cloning {target.org}/{target.repo} (branch: {target.branch})...[/blue]")

    try:
        subprocess.run(
            [
                "git", "clone",
                "--depth=1",
                "--branch", target.branch,
                clone_url,
                str(clone_dir),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip()
        if "Authentication failed" in stderr or "could not read Username" in stderr:
            raise RuntimeError(
                "GitHub authentication failed. Please check your token.\n"
                "Set GITHUB_TOKEN in your .env file or pass --token."
            ) from e
        if "not found" in stderr.lower() or "does not exist" in stderr.lower():
            raise RuntimeError(
                f"Repository not found: {target.clone_url}\n"
                f"Branch: {target.branch}"
            ) from e
        raise RuntimeError(f"git clone failed: {stderr}") from e

    # Verify scope path exists (if specified)
    if target.scope_path:
        scope_dir = clone_dir / target.scope_path
        if not scope_dir.is_dir():
            # List actual directories at that level for helpful error
            parent = clone_dir / Path(target.scope_path).parent
            if parent.is_dir():
                available = [d.name for d in parent.iterdir() if d.is_dir() and not d.name.startswith(".")]
                available_str = ", ".join(sorted(available)) if available else "(none)"
            else:
                available_str = "(parent directory not found)"
            cleanup_clone(target)
            raise RuntimeError(
                f"Scope path '{target.scope_path}' does not exist in the repo.\n"
                f"Available directories: {available_str}"
            )

    console.print(f"[green]Clone complete.[/green]")
    return clone_dir


def get_head_sha(clone_dir: Path) -> str:
    """Get the HEAD commit SHA of the cloned repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=clone_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown"


def is_cache_valid(target: RepoTarget, clone_dir: Path) -> bool:
    """Check if cached analysis is still valid (same commit SHA)."""
    cache_dir = get_cache_dir(target)
    sha_file = cache_dir / "commit_sha.txt"

    if not sha_file.exists():
        return False

    cached_sha = sha_file.read_text().strip()
    current_sha = get_head_sha(clone_dir)

    return cached_sha == current_sha


def save_commit_sha(target: RepoTarget, clone_dir: Path):
    """Save the current HEAD SHA to cache for future validation."""
    cache_dir = get_cache_dir(target)
    cache_dir.mkdir(parents=True, exist_ok=True)
    sha_file = cache_dir / "commit_sha.txt"
    sha_file.write_text(get_head_sha(clone_dir))


def cleanup_clone(target: RepoTarget):
    """Delete the cloned repo."""
    clone_dir = get_clone_dir(target)
    if clone_dir.exists():
        shutil.rmtree(clone_dir, ignore_errors=True)
        console.print("[dim]Clone cleaned up.[/dim]")


def clear_cache(target: RepoTarget):
    """Clear cached analysis for a repo target."""
    cache_dir = get_cache_dir(target)
    if cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)
