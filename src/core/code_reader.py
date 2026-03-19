"""Scope-aware code reader for accessing repository files."""

import os
import re
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchResult:
    file: str
    line_number: int
    line: str
    context_before: list[str]
    context_after: list[str]


# Max lines before we return a summary instead of full content
FILE_SUMMARY_THRESHOLD = 500


class CodeReader:
    """
    Provides structured, scope-aware access to the cloned repository.

    - Scope files: paths relative to scope_path (e.g., "src/main.py")
    - Context files: paths prefixed with ~/ relative to repo root (e.g., "~/shared/auth.py")
    """

    def __init__(self, clone_dir: Path, scope_path: str = ""):
        self.clone_dir = clone_dir
        self.scope_path = scope_path
        self.scope_dir = clone_dir / scope_path if scope_path else clone_dir

        if not self.scope_dir.is_dir():
            raise FileNotFoundError(f"Scope directory not found: {self.scope_dir}")

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path to an absolute path.
        Paths starting with ~/ are relative to repo root.
        Other paths are relative to scope directory.
        """
        if path.startswith("~/"):
            return self.clone_dir / path[2:]
        return self.scope_dir / path

    def _relative_to_scope(self, abs_path: Path) -> str:
        """Convert absolute path to scope-relative or repo-relative string."""
        try:
            return str(abs_path.relative_to(self.scope_dir))
        except ValueError:
            try:
                return "~/" + str(abs_path.relative_to(self.clone_dir))
            except ValueError:
                return str(abs_path)

    def tree(self, depth: int = 3) -> str:
        """Directory tree of the scope directory."""
        return self._build_tree(self.scope_dir, depth=depth, prefix="")

    def tree_root(self, depth: int = 2) -> str:
        """Shallow tree of the full repo root (for context orientation)."""
        return self._build_tree(self.clone_dir, depth=depth, prefix="")

    def _build_tree(self, root: Path, depth: int, prefix: str) -> str:
        if depth < 0:
            return ""

        lines = []
        try:
            entries = sorted(root.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return prefix + "(permission denied)\n"

        # Filter out hidden files and common noise
        skip = {".git", "node_modules", "__pycache__", ".tox", ".mypy_cache",
                ".pytest_cache", "venv", ".venv", ".eggs", "*.egg-info"}
        entries = [e for e in entries if e.name not in skip and not e.name.endswith(".egg-info")]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{prefix}{connector}{entry.name}{suffix}")

            if entry.is_dir() and depth > 0:
                extension = "    " if is_last else "│   "
                sub = self._build_tree(entry, depth - 1, prefix + extension)
                if sub:
                    lines.append(sub.rstrip("\n"))

        return "\n".join(lines)

    def read_file(self, path: str) -> str:
        """Read a file. Files > 500 lines return a summary.
        Use read_file_full() for complete content of large files."""
        abs_path = self._resolve_path(path)

        if not abs_path.is_file():
            return f"[FILE NOT FOUND: {path}]"

        try:
            content = abs_path.read_text(errors="replace")
        except Exception as e:
            return f"[ERROR READING {path}: {e}]"

        lines = content.splitlines()
        if len(lines) <= FILE_SUMMARY_THRESHOLD:
            return self._with_line_numbers(lines)

        # Return summary for large files
        head = lines[:50]
        tail = lines[-20:]
        return (
            f"[FILE SUMMARY — {len(lines)} lines total, showing first 50 + last 20]\n"
            f"--- First 50 lines ---\n"
            f"{self._with_line_numbers(head)}\n"
            f"\n... ({len(lines) - 70} lines omitted) ...\n\n"
            f"--- Last 20 lines ---\n"
            f"{self._with_line_numbers(tail, start=len(lines) - 19)}"
        )

    def read_file_full(self, path: str) -> str:
        """Read complete file content regardless of size."""
        abs_path = self._resolve_path(path)

        if not abs_path.is_file():
            return f"[FILE NOT FOUND: {path}]"

        try:
            content = abs_path.read_text(errors="replace")
            lines = content.splitlines()
            return self._with_line_numbers(lines)
        except Exception as e:
            return f"[ERROR READING {path}: {e}]"

    def _with_line_numbers(self, lines: list[str], start: int = 1) -> str:
        width = len(str(start + len(lines)))
        return "\n".join(
            f"{i:{width}d}  {line}" for i, line in enumerate(lines, start=start)
        )

    def search(self, pattern: str, file_glob: str = "*", scope_only: bool = True) -> list[SearchResult]:
        """Search for a pattern in the codebase."""
        search_dir = self.scope_dir if scope_only else self.clone_dir
        results = []

        try:
            cmd = [
                "grep", "-rnI",  # recursive, line numbers, skip binary
                "--include", file_glob,
                "-B", "2", "-A", "2",  # 2 lines context
                pattern,
                str(search_dir),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            output = proc.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return results

        # Parse grep output
        current_file = None
        current_results = []

        for line in output.splitlines()[:200]:  # Cap at 200 lines
            # Match: filename:lineno:content
            m = re.match(r"^(.+?):(\d+)[:-](.*)$", line)
            if m:
                filepath = m.group(1)
                lineno = int(m.group(2))
                content = m.group(3)

                rel_path = self._relative_to_scope(Path(filepath))
                results.append(SearchResult(
                    file=rel_path,
                    line_number=lineno,
                    line=content,
                    context_before=[],
                    context_after=[],
                ))

        # Deduplicate by file+line
        seen = set()
        unique = []
        for r in results:
            key = (r.file, r.line_number)
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique[:50]  # Cap results

    def search_to_string(self, pattern: str, file_glob: str = "*", scope_only: bool = True) -> str:
        """Search and return results as a formatted string (for LLM consumption)."""
        results = self.search(pattern, file_glob, scope_only)
        if not results:
            return f"No matches found for pattern: {pattern}"

        lines = [f"Found {len(results)} match(es) for '{pattern}':"]
        for r in results:
            lines.append(f"  {r.file}:{r.line_number}  {r.line.strip()}")
        return "\n".join(lines)

    def files_by_extension(self, ext: str) -> list[str]:
        """List all files in scope matching extension."""
        if not ext.startswith("."):
            ext = "." + ext

        results = []
        for root, dirs, files in os.walk(self.scope_dir):
            # Skip hidden and noise directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                       {"node_modules", "__pycache__", "venv", ".venv"}]
            for f in files:
                if f.endswith(ext):
                    rel = os.path.relpath(os.path.join(root, f), self.scope_dir)
                    results.append(rel)
        return sorted(results)

    def dependency_manifests(self) -> dict[str, str]:
        """Find and read dependency manifest files from scope and repo root."""
        manifest_names = [
            "requirements.txt", "Pipfile", "pyproject.toml", "setup.py", "setup.cfg",
            "package.json", "package-lock.json", "yarn.lock",
            "go.mod", "go.sum",
            "pom.xml", "build.gradle", "build.gradle.kts",
            "Cargo.toml", "Gemfile",
        ]

        found = {}

        # Check scope directory
        for name in manifest_names:
            path = self.scope_dir / name
            if path.is_file():
                try:
                    found[str(path.relative_to(self.scope_dir))] = path.read_text(errors="replace")
                except Exception:
                    pass

        # Check repo root (for monorepo root-level manifests)
        if self.scope_path:
            for name in manifest_names:
                path = self.clone_dir / name
                if path.is_file():
                    rel = "~/" + name
                    if rel not in found:
                        try:
                            found[rel] = path.read_text(errors="replace")
                        except Exception:
                            pass

        return found

    def config_files(self) -> dict[str, str]:
        """Find and read configuration files from scope and repo root."""
        config_patterns = [
            ".env.example", ".env.sample", "*.yaml", "*.yml", "*.toml",
            "*.properties", "*.conf", "*.cfg", "*.ini",
        ]
        config_names = [
            "config.yaml", "config.yml", "config.json",
            "settings.py", "settings.yaml", "settings.yml",
            "application.properties", "application.yaml", "application.yml",
            ".env.example", ".env.sample",
            "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
        ]

        found = {}

        # Check scope directory for known config files
        for name in config_names:
            path = self.scope_dir / name
            if path.is_file():
                try:
                    found[str(path.relative_to(self.scope_dir))] = path.read_text(errors="replace")
                except Exception:
                    pass

        # Walk scope for yaml/yml/toml configs (1 level deep only to avoid noise)
        for entry in self.scope_dir.iterdir():
            if entry.is_file() and entry.suffix in (".yaml", ".yml", ".toml", ".json", ".ini", ".cfg"):
                rel = str(entry.relative_to(self.scope_dir))
                if rel not in found:
                    try:
                        found[rel] = entry.read_text(errors="replace")
                    except Exception:
                        pass

        # Check repo root
        if self.scope_path:
            for name in config_names:
                path = self.clone_dir / name
                if path.is_file():
                    rel = "~/" + name
                    if rel not in found:
                        try:
                            found[rel] = path.read_text(errors="replace")
                        except Exception:
                            pass

        return found

    def test_files(self) -> list[str]:
        """List all test file paths in scope."""
        results = []
        for root, dirs, files in os.walk(self.scope_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                       {"node_modules", "__pycache__", "venv", ".venv"}]
            for f in files:
                if (f.startswith("test_") or f.endswith("_test.py") or
                    f.endswith(".test.js") or f.endswith(".test.ts") or
                    f.endswith("_test.go") or f.startswith("Test")):
                    rel = os.path.relpath(os.path.join(root, f), self.scope_dir)
                    results.append(rel)
        return sorted(results)

    def ci_cd_files(self) -> dict[str, str]:
        """Find CI/CD pipeline files."""
        found = {}
        ci_dirs = [".github/workflows", ".gitlab", ".circleci"]
        ci_files = ["Jenkinsfile", ".gitlab-ci.yml", "cloudbuild.yaml", "cloudbuild.json"]

        search_root = self.clone_dir  # CI/CD is usually at repo root

        for ci_dir in ci_dirs:
            ci_path = search_root / ci_dir
            if ci_path.is_dir():
                for f in ci_path.rglob("*"):
                    if f.is_file():
                        rel = "~/" + str(f.relative_to(search_root))
                        try:
                            found[rel] = f.read_text(errors="replace")
                        except Exception:
                            pass

        for name in ci_files:
            path = search_root / name
            if path.is_file():
                rel = "~/" + name
                try:
                    found[rel] = path.read_text(errors="replace")
                except Exception:
                    pass

        return found

    def iac_files(self) -> dict[str, str]:
        """Find Infrastructure-as-Code files (Terraform, K8s manifests)."""
        found = {}
        iac_dirs = ["terraform", "tf", "infra", "infrastructure", "deploy", "k8s", "kubernetes", "helm"]

        for iac_dir_name in iac_dirs:
            # Check in scope
            iac_path = self.scope_dir / iac_dir_name
            if iac_path.is_dir():
                for f in iac_path.rglob("*"):
                    if f.is_file() and f.suffix in (".tf", ".yaml", ".yml", ".json", ".hcl"):
                        rel = str(f.relative_to(self.scope_dir))
                        try:
                            found[rel] = f.read_text(errors="replace")
                        except Exception:
                            pass

            # Check at repo root
            if self.scope_path:
                iac_path = self.clone_dir / iac_dir_name
                if iac_path.is_dir():
                    for f in iac_path.rglob("*"):
                        if f.is_file() and f.suffix in (".tf", ".yaml", ".yml", ".json", ".hcl"):
                            rel = "~/" + str(f.relative_to(self.clone_dir))
                            if rel not in found:
                                try:
                                    found[rel] = f.read_text(errors="replace")
                                except Exception:
                                    pass

        return found

    def is_in_scope(self, path: str) -> bool:
        """Check if a path is within the primary scope directory."""
        return not path.startswith("~/")

    def all_source_files(self) -> list[str]:
        """List all source code files in scope (not tests, not config)."""
        source_exts = {".py", ".go", ".java", ".kt", ".ts", ".js", ".jsx", ".tsx",
                       ".rs", ".rb", ".cs", ".cpp", ".c", ".h", ".proto", ".graphql"}
        results = []
        for root, dirs, files in os.walk(self.scope_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                       {"node_modules", "__pycache__", "venv", ".venv", "test", "tests",
                        "test_data", "testdata", "fixtures"}]
            for f in files:
                if Path(f).suffix in source_exts:
                    rel = os.path.relpath(os.path.join(root, f), self.scope_dir)
                    results.append(rel)
        return sorted(results)
