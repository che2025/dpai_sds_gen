"""Configuration loading from .env and .dpai_sds_gen.yaml."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import yaml
from dotenv import load_dotenv


@dataclass
class SoftwareConfig:
    sw_number: str = "[TBC]"
    sw_name: str = "[TBC]"
    system_name: str = ""


@dataclass
class AnalysisConfig:
    exclude_paths: list[str] = field(default_factory=lambda: [
        "vendor/", "node_modules/", ".git/", "__pycache__/",
        "venv/", ".venv/", ".tox/",
    ])
    entry_points: list[str] = field(default_factory=list)


@dataclass
class ReferenceEntry:
    doc_number: str
    description: str


@dataclass
class LimitsConfig:
    max_cost_usd: float = 20.0
    max_api_calls: int = 200


@dataclass
class AppConfig:
    # From .env
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    gemini_model: str = "gemini-2.5-pro"
    github_token: str = ""

    # From .dpai_sds_gen.yaml
    software: SoftwareConfig = field(default_factory=SoftwareConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    references: list[ReferenceEntry] = field(default_factory=list)
    limits: LimitsConfig = field(default_factory=LimitsConfig)

    # CLI overrides
    output_path: str = ""
    template_path: str = ""
    verbose: bool = False


def load_env(env_path: Optional[str] = None) -> dict:
    """Load environment variables from .env file."""
    if env_path:
        load_dotenv(env_path)
    else:
        # Try current directory, then home
        for path in [Path.cwd() / ".env", Path.home() / ".dpai_sds_gen" / ".env"]:
            if path.exists():
                load_dotenv(path)
                break

    return {
        "google_cloud_project": os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        "google_cloud_location": os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.5-pro"),
        "github_token": os.getenv("GITHUB_TOKEN", ""),
        "max_cost_usd": float(os.getenv("MAX_COST_USD", "20.0")),
        "max_api_calls": int(os.getenv("MAX_API_CALLS", "200")),
    }


def load_yaml_config(yaml_path: Path) -> dict:
    """Load project config from .dpai_sds_gen.yaml."""
    if not yaml_path.exists():
        return {}

    with open(yaml_path) as f:
        return yaml.safe_load(f) or {}


def find_yaml_config(clone_dir: Path, scope_path: str) -> Optional[Path]:
    """Find .dpai_sds_gen.yaml in scope directory or repo root."""
    if scope_path:
        scope_yaml = clone_dir / scope_path / ".dpai_sds_gen.yaml"
        if scope_yaml.exists():
            return scope_yaml

    root_yaml = clone_dir / ".dpai_sds_gen.yaml"
    if root_yaml.exists():
        return root_yaml

    return None


def build_config(
    clone_dir: Optional[Path] = None,
    scope_path: str = "",
    env_path: Optional[str] = None,
    config_path: Optional[str] = None,
    # CLI overrides
    sw_number: Optional[str] = None,
    sw_name: Optional[str] = None,
    model: Optional[str] = None,
    token: Optional[str] = None,
    output: Optional[str] = None,
    template: Optional[str] = None,
    max_cost: Optional[float] = None,
    verbose: bool = False,
) -> AppConfig:
    """Build the complete configuration from all sources."""

    # 1. Load .env
    env = load_env(env_path)

    # 2. Load yaml config
    yaml_data = {}
    if config_path:
        yaml_data = load_yaml_config(Path(config_path))
    elif clone_dir:
        yaml_path = find_yaml_config(clone_dir, scope_path)
        if yaml_path:
            yaml_data = load_yaml_config(yaml_path)

    # 3. Build config with precedence: CLI > yaml > env > defaults
    software_yaml = yaml_data.get("software", {})
    analysis_yaml = yaml_data.get("analysis", {})
    limits_yaml = yaml_data.get("limits", {})

    config = AppConfig(
        google_cloud_project=env.get("google_cloud_project", ""),
        google_cloud_location=env.get("google_cloud_location", "us-central1"),
        gemini_model=model or env.get("gemini_model", "gemini-2.5-pro"),
        github_token=token or env.get("github_token", ""),

        software=SoftwareConfig(
            sw_number=sw_number or software_yaml.get("sw_number", "[TBC]"),
            sw_name=sw_name or software_yaml.get("sw_name", "[TBC]"),
            system_name=software_yaml.get("system_name", ""),
        ),

        analysis=AnalysisConfig(
            exclude_paths=analysis_yaml.get("exclude_paths", AnalysisConfig().exclude_paths),
            entry_points=analysis_yaml.get("entry_points", []),
        ),

        references=[
            ReferenceEntry(r["doc_number"], r["description"])
            for r in yaml_data.get("references", [])
        ],

        limits=LimitsConfig(
            max_cost_usd=max_cost or limits_yaml.get("max_cost_usd", env.get("max_cost_usd", 20.0)),
            max_api_calls=limits_yaml.get("max_api_calls", env.get("max_api_calls", 200)),
        ),

        output_path=output or "",
        template_path=template or "",
        verbose=verbose,
    )

    return config
