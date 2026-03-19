"""Track API call costs and token usage."""

import json
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from rich.console import Console

console = Console()

# Gemini 2.5 Pro pricing (per 1M tokens, approximate)
# Update these as pricing changes
PRICING = {
    "gemini-2.5-pro": {"input": 1.25, "output": 10.0},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
}
DEFAULT_PRICING = {"input": 1.25, "output": 10.0}


@dataclass
class PhaseStats:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class CostTracker:
    phase1: PhaseStats = field(default_factory=PhaseStats)
    phase2: PhaseStats = field(default_factory=PhaseStats)
    model: str = "gemini-2.5-pro"
    max_cost_usd: float = 20.0
    max_api_calls: int = 200
    _save_path: Path = field(default=None, repr=False)

    def record_call(self, phase: str, input_tokens: int, output_tokens: int):
        """Record an API call's token usage."""
        stats = self.phase1 if phase == "phase1" else self.phase2
        stats.calls += 1
        stats.input_tokens += input_tokens
        stats.output_tokens += output_tokens
        self.save()

    @property
    def total_calls(self) -> int:
        return self.phase1.calls + self.phase2.calls

    @property
    def total_input_tokens(self) -> int:
        return self.phase1.input_tokens + self.phase2.input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self.phase1.output_tokens + self.phase2.output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        pricing = PRICING.get(self.model, DEFAULT_PRICING)
        input_cost = (self.total_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.total_output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def check_limits(self):
        """Raise if cost or call limits are exceeded."""
        if self.estimated_cost_usd >= self.max_cost_usd:
            raise RuntimeError(
                f"Cost limit reached: ${self.estimated_cost_usd:.2f} >= ${self.max_cost_usd:.2f}\n"
                "Increase MAX_COST_USD or --max-cost to continue."
            )
        if self.total_calls >= self.max_api_calls:
            raise RuntimeError(
                f"API call limit reached: {self.total_calls} >= {self.max_api_calls}\n"
                "Increase MAX_API_CALLS to continue."
            )

    def warn_if_approaching(self):
        """Warn if approaching 90% of limits."""
        if self.estimated_cost_usd >= self.max_cost_usd * 0.9:
            console.print(
                f"[yellow]⚠ Approaching cost limit: "
                f"${self.estimated_cost_usd:.2f} / ${self.max_cost_usd:.2f}[/yellow]"
            )

    def display(self, phase: str = ""):
        """Display current stats."""
        cost = self.estimated_cost_usd
        console.print(
            f"  API calls: {self.total_calls} | "
            f"Tokens: {self.total_input_tokens:,} in / {self.total_output_tokens:,} out | "
            f"Est. cost: ${cost:.2f}"
        )

    def save(self):
        """Save to disk."""
        if self._save_path:
            data = {
                "phase1": asdict(self.phase1),
                "phase2": asdict(self.phase2),
                "model": self.model,
                "total_estimated_cost_usd": round(self.estimated_cost_usd, 4),
            }
            self._save_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load_or_create(cls, path: Path, model: str = "gemini-2.5-pro",
                       max_cost: float = 20.0, max_calls: int = 200) -> "CostTracker":
        """Load existing tracker or create new one."""
        tracker = cls(model=model, max_cost_usd=max_cost, max_api_calls=max_calls)
        tracker._save_path = path

        if path.exists():
            try:
                data = json.loads(path.read_text())
                tracker.phase1 = PhaseStats(**data.get("phase1", {}))
                tracker.phase2 = PhaseStats(**data.get("phase2", {}))
            except (json.JSONDecodeError, TypeError):
                pass

        return tracker
