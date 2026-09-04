"""Configuration loading for the job agent.

All secrets come from a local `.env` file. The code only reads the
`USER_*` / `GOOGLE_*` / `LINKEDIN_*` / `SCORE_*` variables defined there;
it never touches or scans the agent's own environment for keys.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


def load_dotenv(path: str = ".env") -> None:
    """Minimal .env loader (no external dependency, no override of
    variables already set in the OS environment)."""
    dotenv = Path(path)
    if not dotenv.exists():
        return
    for raw_line in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in ("'", '"')
            and value.count(value[0]) == 2
        ):
            value = value[1:-1]
        if key and not os.environ.get(key):
            os.environ[key] = value


@dataclass
class Config:
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    score_threshold: int = 70

    google_service_account_file: str = "data/service_account.json"
    google_sheet_name: str = "Job Tracker"
    google_sheet_id: str = ""

    search_keywords: str = "python developer"
    search_location: str = "Remote"
    search_pages: int = 2
    search_time_filter: str = "r604800"
    state_file: str = "data/linkedin_state.json"

    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()

        def _get(name: str, default: str = "") -> str:
            return os.environ.get(name, default).strip()

        pages = int(_get("LINKEDIN_PAGES", "2") or 2)
        threshold = int(_get("SCORE_THRESHOLD", "70") or 70)
        return cls(
            llm_api_key=_get("USER_LLM_API_KEY"),
            llm_base_url=_get("USER_LLM_BASE_URL", "https://api.deepseek.com/v1"),
            llm_model=_get("USER_LLM_MODEL", "deepseek-chat"),
            score_threshold=threshold,
            google_service_account_file=_get(
                "GOOGLE_SERVICE_ACCOUNT_FILE", "data/service_account.json"
            ),
            google_sheet_name=_get("GOOGLE_SHEET_NAME", "Job Tracker"),
            google_sheet_id=_get("GOOGLE_SHEET_ID"),
            search_keywords=_get("LINKEDIN_SEARCH_KEYWORDS", "python developer"),
            search_location=_get("LINKEDIN_SEARCH_LOCATION", "Remote"),
            search_pages=pages,
            search_time_filter=_get("LINKEDIN_TIME_FILTER", "r604800"),
            state_file=_get("LINKEDIN_STATE_FILE", "data/linkedin_state.json"),
            extra={
                "profile_file": "profile.md",
                "resume_file": "resume.md",
                "output_dir": "output/tailored",
                "scraped_jobs_file": "data/scraped_jobs.json",
                "rules_file": "rules.yaml",
            },
        )

    def require_llm(self) -> None:
        if not self.llm_api_key or self.llm_api_key == "your-api-key-here":
            raise ConfigError(
                "LLM is not configured. Open `.env`, set USER_LLM_API_KEY to your "
                "own key (see .env.example), then retry."
            )

    def has_llm(self) -> bool:
        return bool(self.llm_api_key) and self.llm_api_key != "your-api-key-here"

    def require_sheets(self) -> None:
        if not os.path.exists(self.google_service_account_file):
            raise ConfigError(
                f"Google service account not found at "
                f"`{self.google_service_account_file}`. Follow the README to create "
                "one and download the JSON here."
            )
