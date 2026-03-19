"""Phase 2 pipeline: generates SDS sections from Phase 1 analysis."""

import json
import re
from pathlib import Path
from typing import Optional

from rich.console import Console

from ..core.code_reader import CodeReader
from ..core.cost_tracker import CostTracker
from ..core.config import AppConfig
from ..llm.adapter import GeminiAdapter
from . import prompts

console = Console()


SECTION_ORDER = [
    "purpose_scope",
    "references",
    "definitions",
    "overview",
    "components",
    "integrations",
    "features",       # Special: per-feature loop
    "ai_principles",
    "security",
    "attachments",
    "definitions_final",
    "quality_check",
]


def _get_section_file(sections_dir: Path, key: str) -> Path:
    """Get the path for a section JSON file."""
    return sections_dir / f"{key}.json"


def _load_section(sections_dir: Path, key: str) -> Optional[dict]:
    """Load a previously generated section from cache."""
    path = _get_section_file(sections_dir, key)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return None
    return None


def _save_section(sections_dir: Path, key: str, data):
    """Save a section JSON to cache."""
    sections_dir.mkdir(parents=True, exist_ok=True)
    path = _get_section_file(sections_dir, key)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _load_all_sections(sections_dir: Path) -> dict:
    """Load all generated section JSONs."""
    all_sections = {}
    if sections_dir.exists():
        for f in sorted(sections_dir.glob("*.json")):
            if f.name != "quality_results.json":
                try:
                    all_sections[f.stem] = json.loads(f.read_text())
                except json.JSONDecodeError:
                    pass
    return all_sections


def _identify_features(analysis_text: str) -> list[dict]:
    """Extract feature names from Phase 1 analysis for per-feature generation."""
    # Look for ## FEATURE: lines or similar patterns
    features = []
    seen = set()

    # Pattern 1: "## FEATURE: Name" or "### Feature: Name"
    for m in re.finditer(r"##+ (?:FEATURE|Feature)[:\s]+(.+)", analysis_text):
        name = m.group(1).strip()
        if name not in seen:
            features.append({"name": name, "section_number": f"6.3.{len(features)+1}"})
            seen.add(name)

    # Pattern 2: "### Purpose" followed by feature-like text
    # If no features found by pattern, create a single generic one
    if not features:
        features.append({"name": "Core Functionality", "section_number": "6.3.1"})

    return features


def _get_previous_sections_summary(all_sections: dict) -> str:
    """Build a summary of previously generated sections for cross-referencing."""
    summary_parts = []
    for key, data in sorted(all_sections.items()):
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "section_number" in item:
                    summary_parts.append(f"Section {item['section_number']}: {item.get('heading', '')}")
        elif isinstance(data, dict) and "section_number" in data:
            summary_parts.append(f"Section {data['section_number']}: {data.get('heading', '')}")
    return "\n".join(summary_parts)


def run_phase2(
    analysis_text: str,
    reader: CodeReader,
    gemini: GeminiAdapter,
    cost_tracker: CostTracker,
    config: AppConfig,
    cache_dir: Path,
) -> Path:
    """
    Run the complete Phase 2 SDS generation pipeline.
    Returns the path to the sections directory.
    """
    sections_dir = cache_dir / "sections"
    sections_dir.mkdir(parents=True, exist_ok=True)

    system_prompt = prompts.core_principles(
        scope_path=reader.scope_path,
        sw_number=config.software.sw_number,
        sw_name=config.software.sw_name,
    )

    console.print("\n[bold blue]═══ Phase 2: SDS Generation ═══[/bold blue]\n")

    step_num = 0
    total_steps = len(SECTION_ORDER)

    for section_key in SECTION_ORDER:
        step_num += 1

        # Skip features — handled separately
        if section_key == "features":
            features = _identify_features(analysis_text)
            for feat in features:
                feat_key = f"feature_{feat['section_number'].replace('.', '_')}"
                cached = _load_section(sections_dir, feat_key)
                if cached:
                    console.print(f"  [dim]Section {feat['section_number']} ({feat['name']}) — cached[/dim]")
                    continue

                console.print(f"[bold]  Generating Section {feat['section_number']}: {feat['name']}[/bold]")

                instructions = prompts.SECTION_INSTRUCTIONS["feature"].format(
                    section_number=feat["section_number"],
                    feature_name=feat["name"],
                )
                task = prompts.SECTION_TASKS["feature"].format(
                    section_number=feat["section_number"],
                    feature_name=feat["name"],
                )

                all_sections = _load_all_sections(sections_dir)
                prev_summary = _get_previous_sections_summary(all_sections)

                user_message = (
                    f"Phase 1 analysis:\n{analysis_text}\n\n"
                    f"Previously generated sections:\n{prev_summary}\n\n"
                    f"{task}"
                )

                section_system = system_prompt + "\n\n" + instructions
                result = gemini.generate_json(
                    system_prompt=section_system,
                    user_message=user_message,
                    code_reader=None,
                    enable_function_calling=False,
                    phase="phase2",
                )
                _save_section(sections_dir, feat_key, result)
                cost_tracker.display()
            continue

        # Check cache
        cached = _load_section(sections_dir, section_key)
        if cached and section_key not in ("definitions_final", "quality_check"):
            console.print(f"  [dim]Step {step_num}/{total_steps}: {section_key} — cached[/dim]")
            continue

        console.print(f"[bold]Step {step_num}/{total_steps}: {section_key}[/bold]")

        instructions = prompts.SECTION_INSTRUCTIONS.get(section_key, "")
        task = prompts.SECTION_TASKS.get(section_key, "")

        # Build context
        all_sections = _load_all_sections(sections_dir)
        prev_summary = _get_previous_sections_summary(all_sections)

        # Special handling for certain sections
        extra_context = ""
        if section_key == "references":
            # Include user-provided references from config
            if config.references:
                refs = "\n".join(f"- {r.doc_number}: {r.description}" for r in config.references)
                extra_context = f"\nUser-provided references:\n{refs}\n"

        elif section_key == "definitions_final":
            # Include current definitions and all section content
            current_defs = _load_section(sections_dir, "definitions")
            all_content = json.dumps(all_sections, indent=2, ensure_ascii=False)
            extra_context = (
                f"\nCurrent definitions:\n{json.dumps(current_defs, indent=2, ensure_ascii=False)}\n"
                f"\nAll section content:\n{all_content}\n"
            )

        elif section_key == "quality_check":
            all_content = json.dumps(all_sections, indent=2, ensure_ascii=False)
            extra_context = f"\nComplete SDS content:\n{all_content}\n"

        elif section_key == "attachments":
            all_content = json.dumps(all_sections, indent=2, ensure_ascii=False)
            extra_context = f"\nAll sections (scan for TBC):\n{all_content}\n"

        user_message = (
            f"Phase 1 analysis:\n{analysis_text}\n\n"
            f"Previously generated sections:\n{prev_summary}\n"
            f"{extra_context}\n"
            f"{task}"
        )

        section_system = system_prompt + "\n\n" + instructions

        result = gemini.generate_json(
            system_prompt=section_system,
            user_message=user_message,
            code_reader=None,
            enable_function_calling=False,
            phase="phase2",
        )

        _save_section(sections_dir, section_key, result)
        cost_tracker.display()
        console.print(f"  [green]✓ {section_key} complete[/green]\n")

    # Handle quality check results
    quality_results = _load_section(sections_dir, "quality_check")
    if quality_results and "validation_results" in quality_results:
        _apply_fixes(sections_dir, quality_results["validation_results"])

    # If definitions_final was generated, replace the original definitions
    final_defs = _load_section(sections_dir, "definitions_final")
    if final_defs:
        _save_section(sections_dir, "definitions", final_defs)

    console.print("[green]Phase 2 generation complete.[/green]")
    return sections_dir


def _apply_fixes(sections_dir: Path, validation_results: list):
    """Apply FAIL fixes from quality validation."""
    fail_count = 0
    warn_count = 0

    for result in validation_results:
        if not isinstance(result, dict):
            continue
        severity = result.get("severity", "")
        if severity == "FAIL" and result.get("fix"):
            fail_count += 1
            console.print(f"  [red]FAIL[/red] {result.get('section', '?')}: {result.get('description', '')[:100]}")
            # Auto-fix would require mapping back to the exact section file and content block
            # For now, just log it
        elif severity == "WARN":
            warn_count += 1
            console.print(f"  [yellow]WARN[/yellow] {result.get('section', '?')}: {result.get('description', '')[:100]}")

    if fail_count:
        console.print(f"\n  [red]{fail_count} FAIL item(s) found — review in generated document.[/red]")
    if warn_count:
        console.print(f"  [yellow]{warn_count} WARN item(s) — consider addressing in final review.[/yellow]")


def regenerate_section(
    section_key: str,
    analysis_text: str,
    reader: CodeReader,
    gemini: GeminiAdapter,
    cost_tracker: CostTracker,
    config: AppConfig,
    cache_dir: Path,
):
    """Regenerate a specific section."""
    sections_dir = cache_dir / "sections"

    # Delete cached version
    path = _get_section_file(sections_dir, section_key)
    if path.exists():
        path.unlink()

    # Also try feature pattern
    for f in sections_dir.glob(f"feature_*{section_key.replace('.', '_')}*"):
        f.unlink()

    console.print(f"[blue]Regenerating section: {section_key}[/blue]")

    # Re-run phase 2 — it will skip cached sections and only generate the deleted one
    run_phase2(analysis_text, reader, gemini, cost_tracker, config, cache_dir)
