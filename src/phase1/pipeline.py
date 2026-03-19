"""Phase 1 pipeline: orchestrates code analysis steps 1-10."""

import json
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..core.code_reader import CodeReader
from ..core.cost_tracker import CostTracker
from ..llm.adapter import GeminiAdapter
from . import prompts

console = Console()

STEP_NAMES = {
    1: "Structural Map",
    2: "Build/Deploy/Config",
    3: "Dependencies & Integrations",
    4: "API Surface",
    5: "Data Models",
    6: "Feature & Business Logic",
    7: "Safety & Error Handling",
    8: "Security & Privacy",
    9: "Test Suite",
    10: "Synthesis & Gap Assessment",
}


def _gather_files_for_step(step: int, reader: CodeReader) -> str:
    """Gather relevant files for a given step."""
    files_content = []

    def add_files(file_dict: dict, label: str = ""):
        for path, content in file_dict.items():
            # Truncate very large files
            if len(content) > 50000:
                content = content[:50000] + "\n... (truncated)"
            files_content.append(f"--- File: {path} ---\n{content}")

    def add_file_list(paths: list[str], reader: CodeReader, max_files: int = 30):
        for path in paths[:max_files]:
            content = reader.read_file(path)
            files_content.append(f"--- File: {path} ---\n{content}")

    if step == 1:
        # Structure: tree + config files + README
        files_content.append(f"--- Scope Directory Tree ---\n{reader.tree(depth=3)}")
        if reader.scope_path:
            files_content.append(f"--- Repo Root Tree ---\n{reader.tree_root(depth=2)}")
        add_files(reader.config_files())
        # Try to read README
        for name in ["README.md", "readme.md", "README.rst", "README.txt"]:
            content = reader.read_file(name)
            if not content.startswith("[FILE NOT FOUND"):
                files_content.append(f"--- File: {name} (READ WITH SKEPTICISM) ---\n{content}")
                break

    elif step == 2:
        add_files(reader.config_files())
        add_files(reader.ci_cd_files())
        add_files(reader.iac_files())
        # Dockerfiles
        for name in ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"]:
            content = reader.read_file(name)
            if not content.startswith("[FILE NOT FOUND"):
                files_content.append(f"--- File: {name} ---\n{content}")

    elif step == 3:
        add_files(reader.dependency_manifests())
        # Search for HTTP clients, SDK instantiations
        for pattern in ["import requests", "import httpx", "from google", "import axios",
                        "BigQuery", "VertexAI", "openai", "Pub/Sub", "pubsub"]:
            results = reader.search_to_string(pattern, "*.py", scope_only=True)
            if "No matches" not in results:
                files_content.append(f"--- Search: {pattern} ---\n{results}")
        # Also search in Go, JS, Java
        for pattern in ["http.Client", "fetch(", "HttpClient"]:
            for glob in ["*.go", "*.ts", "*.js", "*.java"]:
                results = reader.search_to_string(pattern, glob, scope_only=True)
                if "No matches" not in results:
                    files_content.append(f"--- Search: {pattern} ({glob}) ---\n{results}")

    elif step == 4:
        # Find route handlers, API definitions
        for pattern in ["@app.route", "@router.", "HandleFunc", "@GetMapping", "@PostMapping",
                        "@RequestMapping", "router.get", "router.post", "app.get(", "app.post("]:
            results = reader.search_to_string(pattern, "*", scope_only=True)
            if "No matches" not in results:
                files_content.append(f"--- Search: {pattern} ---\n{results}")
        # Look for OpenAPI specs
        for name in ["swagger.json", "swagger.yaml", "openapi.json", "openapi.yaml"]:
            content = reader.read_file(name)
            if not content.startswith("[FILE NOT FOUND"):
                files_content.append(f"--- File: {name} ---\n{content}")
        # Proto files
        proto_files = reader.files_by_extension(".proto")
        add_file_list(proto_files, reader, max_files=10)

    elif step == 5:
        # ORM models, migrations, DTOs
        for pattern in ["class.*Model", "Base.metadata", "declarative_base", "models.Model",
                        "BaseModel", "dataclass", "@dataclass", "message.*{",
                        "CREATE TABLE", "db.Column"]:
            results = reader.search_to_string(pattern, "*", scope_only=True)
            if "No matches" not in results:
                files_content.append(f"--- Search: {pattern} ---\n{results}")
        # Look for model/schema directories
        for dirname in ["models", "schemas", "entities", "dto", "migrations"]:
            model_files = [f for f in reader.all_source_files() if dirname in f]
            add_file_list(model_files[:15], reader)

    elif step == 6:
        # This step is special — called per feature. Files are loaded by the caller.
        # Provide all source files as a starting point
        source_files = reader.all_source_files()
        add_file_list(source_files, reader, max_files=40)

    elif step == 7:
        # Error handling, safety
        for pattern in ["except", "try:", "raise", "catch", "throw",
                        "SAFETY", "WARNING", "CRITICAL", "TODO.*safe", "FIXME",
                        "circuit.breaker", "retry", "fallback", "health.*check"]:
            results = reader.search_to_string(pattern, "*", scope_only=True)
            if "No matches" not in results:
                files_content.append(f"--- Search: {pattern} ---\n{results}")

    elif step == 8:
        # Security
        for pattern in ["jwt", "JWT", "oauth", "OAuth", "token", "auth", "TLS", "tls",
                        "encrypt", "decrypt", "secret", "password", "credential",
                        "audit", "rbac", "permission", "mTLS", "certificate"]:
            results = reader.search_to_string(pattern, "*", scope_only=True)
            if "No matches" not in results:
                files_content.append(f"--- Search: {pattern} ---\n{results}")

    elif step == 9:
        test_files = reader.test_files()
        add_file_list(test_files, reader, max_files=30)
        # CI/CD for quality gates
        add_files(reader.ci_cd_files())

    elif step == 10:
        # Synthesis — no new files, uses accumulated analysis
        pass

    return "\n\n".join(files_content)


def run_phase1(
    reader: CodeReader,
    gemini: GeminiAdapter,
    cost_tracker: CostTracker,
    cache_dir: Path,
    scope_path: str = "",
    verbose: bool = False,
) -> str:
    """
    Run the complete Phase 1 analysis pipeline.
    Returns the analysis text and saves it to cache_dir/analysis.md.
    """
    analysis_path = cache_dir / "analysis.md"

    # Check if analysis already exists
    if analysis_path.exists():
        console.print("[green]Phase 1 analysis found in cache. Skipping.[/green]")
        return analysis_path.read_text()

    system_prompt = prompts.core_principles(scope_path)
    accumulated_analysis = []

    console.print("\n[bold blue]═══ Phase 1: Code Analysis ═══[/bold blue]\n")

    for step in range(1, 11):
        step_name = STEP_NAMES[step]
        console.print(f"[bold]Step {step}/10: {step_name}[/bold]")

        # Build step-specific system prompt
        step_system = system_prompt + "\n\n" + prompts.STEP_INSTRUCTIONS.get(step, "")

        # Gather files
        if step == 10:
            # Synthesis uses accumulated analysis, no new files
            files_content = ""
        else:
            files_content = _gather_files_for_step(step, reader)

        # Build user message
        task_prompt = prompts.TASK_PROMPTS.get(step, "")

        # For step 6, we need to identify features first then analyze each
        if step == 6:
            # First, ask LLM to identify features from what we know so far
            identify_prompt = (
                f"Based on the analysis so far, identify the main features/modules "
                f"in this software that need individual deep-dive analysis.\n\n"
                f"Previous analysis:\n{chr(10).join(accumulated_analysis[-3:])}\n\n"
                f"List each feature with: name, brief description, and key source files.\n"
                f"Output as a simple list."
            )
            features_response = gemini.generate(
                system_prompt=step_system,
                user_message=identify_prompt,
                code_reader=reader,
                enable_function_calling=True,
                phase="phase1",
            )
            cost_tracker.display()

            # Then analyze each feature (simplified: do one combined deep dive)
            user_message = (
                f"Previous analysis:\n{chr(10).join(accumulated_analysis[-3:])}\n\n"
                f"Identified features:\n{features_response}\n\n"
                f"Source files:\n{files_content}\n\n"
                f"{task_prompt.replace('{feature_name}', 'ALL FEATURES')}\n\n"
                f"Analyze ALL identified features. For each, provide the complete analysis."
            )
        else:
            context = ""
            if accumulated_analysis:
                # Include last 2 step results as context
                recent = accumulated_analysis[-2:]
                context = f"Analysis from previous steps:\n{'---'.join(recent)}\n\n"

            user_message = f"{context}Files for analysis:\n{files_content}\n\n{task_prompt}"

        # Call LLM
        response = gemini.generate(
            system_prompt=step_system,
            user_message=user_message,
            code_reader=reader,
            enable_function_calling=True,
            phase="phase1",
        )

        accumulated_analysis.append(f"# Step {step}: {step_name}\n\n{response}")
        cost_tracker.display()
        console.print(f"  [green]✓ Step {step} complete[/green]\n")

    # Compile final analysis document
    analysis_text = _compile_analysis(accumulated_analysis, scope_path)

    # Save to cache
    cache_dir.mkdir(parents=True, exist_ok=True)
    analysis_path.write_text(analysis_text)
    console.print(f"[green]Phase 1 analysis saved to cache.[/green]")

    return analysis_text


def _compile_analysis(step_results: list[str], scope_path: str) -> str:
    """Compile step results into the final analysis.md document."""
    header = f"""# Phase 1 Analysis Output

## META
- Scope Path: {scope_path or '(full repository)'}
- Analysis Steps Completed: {len(step_results)}/10

---

"""
    body = "\n\n---\n\n".join(step_results)
    return header + body
