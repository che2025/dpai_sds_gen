"""dpai_sds_gen CLI — main entry point."""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from ..core.url_parser import parse_github_url
from ..core.repo_manager import (
    clone_repo, cleanup_clone, get_cache_dir, get_clone_dir,
    is_cache_valid, save_commit_sha, clear_cache,
)
from ..core.code_reader import CodeReader
from ..core.config import build_config, load_env
from ..core.cost_tracker import CostTracker
from ..llm.adapter import GeminiAdapter
from ..phase1.pipeline import run_phase1
from ..phase2.pipeline import run_phase2, regenerate_section
from ..docx_engine.assembler import assemble_docx

console = Console()
app = typer.Typer(
    name="dpai_sds_gen",
    help="AI-driven SDS generator for IEC 62304 medical device software.",
    add_completion=False,
)


def _setup(
    url: str,
    token: Optional[str] = None,
    sw_number: Optional[str] = None,
    sw_name: Optional[str] = None,
    model: Optional[str] = None,
    output: Optional[str] = None,
    template: Optional[str] = None,
    config_path: Optional[str] = None,
    max_cost: Optional[float] = None,
    verbose: bool = False,
    reanalyze: bool = False,
):
    """Common setup for all commands: parse URL, load config, clone repo."""
    # Load env first (for GitHub token and Vertex AI settings)
    load_env()

    # Parse URL
    try:
        target = parse_github_url(url)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold]Target: {target.display_name}[/bold]")
    console.print(f"  Branch: {target.branch}")
    if target.scope_path:
        console.print(f"  Scope: {target.scope_path}")

    # Build initial config (without clone dir — we'll update after clone)
    config = build_config(
        sw_number=sw_number,
        sw_name=sw_name,
        model=model,
        token=token,
        output=output,
        template=template,
        max_cost=max_cost,
        verbose=verbose,
        config_path=config_path,
    )

    # Clone repo
    effective_token = config.github_token
    try:
        clone_dir = clone_repo(target, token=effective_token)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    # Rebuild config with clone dir (picks up .dpai_sds_gen.yaml from repo)
    config = build_config(
        clone_dir=clone_dir,
        scope_path=target.scope_path,
        sw_number=sw_number,
        sw_name=sw_name,
        model=model,
        token=token,
        output=output,
        template=template,
        max_cost=max_cost,
        verbose=verbose,
        config_path=config_path,
    )

    # Cache dir
    cache_dir = get_cache_dir(target)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Check cache validity
    if reanalyze:
        clear_cache(target)
    elif not is_cache_valid(target, clone_dir):
        console.print("[yellow]Code has changed since last analysis. Re-analyzing.[/yellow]")
        clear_cache(target)

    save_commit_sha(target, clone_dir)

    # Code reader
    reader = CodeReader(clone_dir, target.scope_path)

    # Cost tracker
    cost_tracker = CostTracker.load_or_create(
        path=cache_dir / "cost.json",
        model=config.gemini_model,
        max_cost=config.limits.max_cost_usd,
        max_calls=config.limits.max_api_calls,
    )

    # Gemini adapter
    gemini = GeminiAdapter(
        model=config.gemini_model,
        cost_tracker=cost_tracker,
        verbose=config.verbose,
    )

    return target, config, clone_dir, cache_dir, reader, cost_tracker, gemini


@app.command()
def run(
    url: str = typer.Argument(..., help="GitHub repository URL"),
    token: Optional[str] = typer.Option(None, "--token", help="GitHub token"),
    sw_number: Optional[str] = typer.Option(None, "--sw-number", help="Software identifier"),
    sw_name: Optional[str] = typer.Option(None, "--sw-name", help="Software name"),
    model: Optional[str] = typer.Option(None, "--model", help="Gemini model"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output .docx path"),
    template: Optional[str] = typer.Option(None, "--template", help="Custom .docx template"),
    config_path: Optional[str] = typer.Option(None, "--config", help="Config file path"),
    max_cost: Optional[float] = typer.Option(None, "--max-cost", help="Max cost in USD"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    reanalyze: bool = typer.Option(False, "--reanalyze", help="Force Phase 1 re-run"),
    keep_clone: bool = typer.Option(False, "--keep-clone", help="Don't delete clone after completion"),
):
    """Full pipeline: clone → analyze → generate → assemble .docx."""
    target, config, clone_dir, cache_dir, reader, cost_tracker, gemini = _setup(
        url, token, sw_number, sw_name, model, output, template, config_path, max_cost, verbose, reanalyze,
    )

    try:
        # Phase 1
        analysis_text = run_phase1(
            reader=reader,
            gemini=gemini,
            cost_tracker=cost_tracker,
            cache_dir=cache_dir,
            scope_path=target.scope_path,
            verbose=config.verbose,
        )

        # Phase 2
        sections_dir = run_phase2(
            analysis_text=analysis_text,
            reader=reader,
            gemini=gemini,
            cost_tracker=cost_tracker,
            config=config,
            cache_dir=cache_dir,
        )

        # Assemble .docx
        output_path = Path(config.output_path or f"SDS-{config.software.sw_number}.docx")
        template_path = Path(config.template_path) if config.template_path else None

        assemble_docx(
            sections_dir=sections_dir,
            output_path=output_path,
            sw_number=config.software.sw_number,
            sw_name=config.software.sw_name,
            template_path=template_path,
        )

        # Final cost summary
        console.print("\n[bold]Cost Summary:[/bold]")
        cost_tracker.display()

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Progress saved to cache.[/yellow]")
    except RuntimeError as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        if not keep_clone:
            cleanup_clone(target)


@app.command()
def analyze(
    url: str = typer.Argument(..., help="GitHub repository URL"),
    token: Optional[str] = typer.Option(None, "--token"),
    sw_number: Optional[str] = typer.Option(None, "--sw-number"),
    sw_name: Optional[str] = typer.Option(None, "--sw-name"),
    model: Optional[str] = typer.Option(None, "--model"),
    config_path: Optional[str] = typer.Option(None, "--config"),
    max_cost: Optional[float] = typer.Option(None, "--max-cost"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    reanalyze: bool = typer.Option(False, "--reanalyze"),
    keep_clone: bool = typer.Option(False, "--keep-clone"),
):
    """Phase 1 only: analyze the codebase."""
    target, config, clone_dir, cache_dir, reader, cost_tracker, gemini = _setup(
        url, token, sw_number, sw_name, model, None, None, config_path, max_cost, verbose, reanalyze,
    )

    try:
        run_phase1(
            reader=reader,
            gemini=gemini,
            cost_tracker=cost_tracker,
            cache_dir=cache_dir,
            scope_path=target.scope_path,
            verbose=config.verbose,
        )
        console.print("\n[green]Phase 1 analysis complete. Run 'dpai_sds_gen generate' to create the SDS.[/green]")
        cost_tracker.display()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Progress saved.[/yellow]")
    except RuntimeError as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        if not keep_clone:
            cleanup_clone(target)


@app.command()
def generate(
    url: str = typer.Argument(..., help="GitHub repository URL"),
    token: Optional[str] = typer.Option(None, "--token"),
    sw_number: Optional[str] = typer.Option(None, "--sw-number"),
    sw_name: Optional[str] = typer.Option(None, "--sw-name"),
    model: Optional[str] = typer.Option(None, "--model"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
    template: Optional[str] = typer.Option(None, "--template"),
    config_path: Optional[str] = typer.Option(None, "--config"),
    max_cost: Optional[float] = typer.Option(None, "--max-cost"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    keep_clone: bool = typer.Option(False, "--keep-clone"),
):
    """Phase 2 only: generate SDS from cached analysis."""
    target, config, clone_dir, cache_dir, reader, cost_tracker, gemini = _setup(
        url, token, sw_number, sw_name, model, output, template, config_path, max_cost, verbose,
    )

    # Check that Phase 1 has been run
    analysis_path = cache_dir / "analysis.md"
    if not analysis_path.exists():
        console.print("[red]No Phase 1 analysis found. Run 'dpai_sds_gen analyze' first.[/red]")
        cleanup_clone(target)
        raise typer.Exit(1)

    try:
        analysis_text = analysis_path.read_text()

        sections_dir = run_phase2(
            analysis_text=analysis_text,
            reader=reader,
            gemini=gemini,
            cost_tracker=cost_tracker,
            config=config,
            cache_dir=cache_dir,
        )

        output_path = Path(config.output_path or f"SDS-{config.software.sw_number}.docx")
        template_path = Path(config.template_path) if config.template_path else None

        assemble_docx(
            sections_dir=sections_dir,
            output_path=output_path,
            sw_number=config.software.sw_number,
            sw_name=config.software.sw_name,
            template_path=template_path,
        )

        cost_tracker.display()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Progress saved.[/yellow]")
    except RuntimeError as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        if not keep_clone:
            cleanup_clone(target)


@app.command()
def regenerate(
    url: str = typer.Argument(..., help="GitHub repository URL"),
    section: str = typer.Option(..., "--section", "-s", help="Section key to regenerate"),
    token: Optional[str] = typer.Option(None, "--token"),
    sw_number: Optional[str] = typer.Option(None, "--sw-number"),
    sw_name: Optional[str] = typer.Option(None, "--sw-name"),
    model: Optional[str] = typer.Option(None, "--model"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
    config_path: Optional[str] = typer.Option(None, "--config"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    keep_clone: bool = typer.Option(False, "--keep-clone"),
):
    """Regenerate a specific SDS section."""
    target, config, clone_dir, cache_dir, reader, cost_tracker, gemini = _setup(
        url, token, sw_number, sw_name, model, output, None, config_path, None, verbose,
    )

    analysis_path = cache_dir / "analysis.md"
    if not analysis_path.exists():
        console.print("[red]No Phase 1 analysis found. Run 'dpai_sds_gen run' first.[/red]")
        cleanup_clone(target)
        raise typer.Exit(1)

    try:
        analysis_text = analysis_path.read_text()
        regenerate_section(
            section_key=section,
            analysis_text=analysis_text,
            reader=reader,
            gemini=gemini,
            cost_tracker=cost_tracker,
            config=config,
            cache_dir=cache_dir,
        )

        # Re-assemble docx
        sections_dir = cache_dir / "sections"
        output_path = Path(config.output_path or f"SDS-{config.software.sw_number}.docx")
        assemble_docx(
            sections_dir=sections_dir,
            output_path=output_path,
            sw_number=config.software.sw_number,
            sw_name=config.software.sw_name,
        )
    finally:
        if not keep_clone:
            cleanup_clone(target)


@app.command()
def validate(
    url: str = typer.Argument(..., help="GitHub repository URL"),
    token: Optional[str] = typer.Option(None, "--token"),
    config_path: Optional[str] = typer.Option(None, "--config"),
):
    """Validate generated SDS against completeness checklist."""
    load_env()
    target = parse_github_url(url)
    cache_dir = get_cache_dir(target)
    sections_dir = cache_dir / "sections"

    if not sections_dir.exists():
        console.print("[red]No generated sections found. Run 'dpai_sds_gen run' first.[/red]")
        raise typer.Exit(1)

    # Check which sections exist
    expected = ["purpose_scope", "references", "definitions", "overview",
                "components", "integrations", "security", "attachments"]
    missing = []
    present = []

    for key in expected:
        path = sections_dir / f"{key}.json"
        if path.exists():
            present.append(key)
        else:
            missing.append(key)

    feature_files = list(sections_dir.glob("feature_*.json"))

    console.print("\n[bold]SDS Validation Report[/bold]\n")
    console.print(f"  Sections present: {len(present)}/{len(expected)}")
    console.print(f"  Feature sections: {len(feature_files)}")

    if missing:
        console.print(f"\n  [red]Missing sections:[/red]")
        for m in missing:
            console.print(f"    - {m}")
    else:
        console.print(f"\n  [green]All core sections present.[/green]")

    # Count TBC items
    tbc_count = 0
    for f in sections_dir.glob("*.json"):
        try:
            content = f.read_text()
            tbc_count += content.count("[TBC")
        except Exception:
            pass

    console.print(f"\n  TBC items found: {tbc_count}")
    if tbc_count > 0:
        console.print("  [yellow]Review the .docx for yellow-highlighted TBC items.[/yellow]")


@app.command()
def auth():
    """Set up GitHub credentials."""
    console.print("[bold]GitHub Authentication Setup[/bold]\n")
    token = typer.prompt("Enter your GitHub Personal Access Token (PAT)")

    cred_dir = Path.home() / ".dpai_sds_gen"
    cred_dir.mkdir(parents=True, exist_ok=True)

    env_file = cred_dir / ".env"
    # Read existing env or create new
    existing = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()

    existing["GITHUB_TOKEN"] = token
    env_content = "\n".join(f"{k}={v}" for k, v in existing.items())
    env_file.write_text(env_content + "\n")

    console.print(f"[green]Token saved to {env_file}[/green]")


if __name__ == "__main__":
    app()
