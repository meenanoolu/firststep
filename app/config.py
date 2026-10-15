"""Runtime settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _intervals() -> tuple[int, ...]:
    raw = os.environ.get("REVIEW_INTERVALS_DAYS", "1,3,7,21")
    try:
        vals = tuple(int(x) for x in raw.split(",") if x.strip())
    except ValueError:
        vals = ()
    return vals or (1, 3, 7, 21)


@dataclass(frozen=True)
class Settings:
    db_path: str = field(default_factory=lambda: os.environ.get("DB_PATH", str(ROOT / "data" / "firststep.db")))
    dev_mode: bool = field(default_factory=lambda: _flag("DEV_MODE", False))
    store_code: bool = field(default_factory=lambda: _flag("STORE_CODE", True))
    store_first_steps: bool = field(default_factory=lambda: _flag("STORE_FIRST_STEPS", True))
    max_concurrent_runs: int = field(default_factory=lambda: _int("MAX_CONCURRENT_RUNS", 2))
    max_submits_per_day: int = field(default_factory=lambda: _int("MAX_SUBMITS_PER_DAY", 80))
    run_timeout_s: float = field(default_factory=lambda: float(os.environ.get("RUN_TIMEOUT_S", "2.0")))
    finder_budget: int = field(default_factory=lambda: _int("FINDER_BUDGET", 150))
    shrink_budget: int = field(default_factory=lambda: _int("SHRINK_BUDGET", 80))
    review_intervals_days: tuple[int, ...] = field(default_factory=_intervals)

    payment_url: str = field(default_factory=lambda: os.environ.get("PAYMENT_URL", ""))
    payment_label: str = field(default_factory=lambda: os.environ.get("PAYMENT_LABEL", "Book a 30-min coaching session that uses this tool"))

    llm_provider: str = field(default_factory=lambda: os.environ.get("LLM_PROVIDER", "none").lower())
    ollama_url: str = field(default_factory=lambda: os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.environ.get("OLLAMA_MODEL", "gemma4:e4b"))
    llm_base_url: str = field(default_factory=lambda: os.environ.get("LLM_BASE_URL", ""))
    llm_api_key: str = field(default_factory=lambda: os.environ.get("LLM_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", ""))


def get_settings() -> Settings:
    return Settings()