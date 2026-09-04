"""Central, env-driven configuration.

Per AGENT.md's "scale by config, not by rewrite" rule: concurrency, source lists,
and provider order all live here so going from 1k -> 500k records is a config
change (or infra change), not a code change.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv


def load_env() -> None:
    """Load .env file into os.environ from project root.

    Searches upward from this file's directory for .env, then the current working
    directory, so it works regardless of where the pipeline is invoked from.
    """
    search_paths = [
        Path(__file__).resolve().parents[1],
        Path.cwd(),
    ]
    for path in search_paths:
        env_file = path / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            return


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


def _env_list(key: str, default: List[str]) -> List[str]:
    raw = os.environ.get(key)
    return [s.strip() for s in raw.split(",")] if raw else default


@dataclass
class Settings:
    # --- Concurrency / scale knobs ---
    max_concurrent_requests_per_domain: int = field(
        default_factory=lambda: _env_int("MAX_CONCURRENT_PER_DOMAIN", 5)
    )
    max_global_concurrency: int = field(
        default_factory=lambda: _env_int("MAX_GLOBAL_CONCURRENCY", 50)
    )
    request_timeout_seconds: int = field(
        default_factory=lambda: _env_int("REQUEST_TIMEOUT_SECONDS", 30)
    )

    # --- Freshness window ---
    freshness_window_hours: int = field(
        default_factory=lambda: _env_int("FRESHNESS_WINDOW_HOURS", 24)
    )

    # --- LLM provider chain (order matters: cheapest/fastest first) ---
    llm_provider_chain: List[str] = field(
        default_factory=lambda: _env_list("LLM_PROVIDER_CHAIN", ["gemini", "groq", "deepseek"])
    )
    llm_max_retries_per_provider: int = field(
        default_factory=lambda: _env_int("LLM_MAX_RETRIES_PER_PROVIDER", 2)
    )
    llm_backoff_base_seconds: float = field(
        default_factory=lambda: float(os.environ.get("LLM_BACKOFF_BASE_SECONDS", "1.0"))
    )
    llm_backoff_cap_seconds: float = field(
        default_factory=lambda: float(os.environ.get("LLM_BACKOFF_CAP_SECONDS", "30.0"))
    )
    llm_max_input_tokens: int = field(
        default_factory=lambda: _env_int("LLM_MAX_INPUT_TOKENS", 6000)
    )

    # --- API keys (loaded from .env; never commit real values) ---
    gemini_api_key: str = field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))
    groq_api_key: str = field(default_factory=lambda: os.environ.get("GROQ_API_KEY", ""))
    deepseek_api_key: str = field(default_factory=lambda: os.environ.get("DEEPSEEK_API_KEY", ""))
    github_token: str = field(default_factory=lambda: os.environ.get("GITHUB_TOKEN", ""))

    # --- Sources (edit freely; this is the "scale via config" surface) ---
    news_sources: List[str] = field(
        default_factory=lambda: _env_list(
            "NEWS_SOURCES",
            [
                "https://techcrunch.com/category/artificial-intelligence/",
                "https://venturebeat.com/category/ai/",
                "https://www.theverge.com/ai-artificial-intelligence",
                "https://www.artificialintelligence-news.com/",
                "https://www.marktechpost.com/",
            ],
        )
    )
    job_board_sources: List[str] = field(
        default_factory=lambda: _env_list(
            "JOB_BOARD_SOURCES",
            [
                "https://www.ycombinator.com/jobs/role/ai-ml",
                "https://weworkremotely.com/categories/remote-artificial-intelligence-jobs",
                "https://www.remote.co/remote-jobs/machine-learning",
                "https://ai-jobs.net/",
                "https://www.builtin.com/jobs/artificial-intelligence",
            ],
        )
    )

    # --- Storage ---
    database_url: str = field(
        default_factory=lambda: os.environ.get("DATABASE_URL", "sqlite:///./data/pipeline.db")
    )
    google_sheets_id: str = field(default_factory=lambda: os.environ.get("GOOGLE_SHEETS_ID", ""))
    google_service_account_json: str = field(
        default_factory=lambda: os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    )


load_env()

settings = Settings()
