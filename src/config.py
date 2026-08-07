import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

import yaml


@dataclass
class Source:
    name: str
    url: str
    category: str
    language: str = "en"
    enabled: bool = True
    allowed_categories: List[str] = field(default_factory=list)


@dataclass
class Filters:
    keywords: List[str] = field(default_factory=list)
    required_in_title: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)


@dataclass
class Settings:
    lookback_hours: int = 48
    max_per_source: int = 15
    timezone: str = "America/New_York"
    site_name: str = "US Trend Brief"
    site_description: str = ""


@dataclass
class Config:
    sources: List[Source]
    filters: Filters
    settings: Settings


def load_config(path: Optional[Union[str, Path]] = None) -> Config:
    if path is None:
        repo_root = Path(__file__).resolve().parent.parent
        path = repo_root / "config" / "sources.yaml"

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    sources = [Source(**s) for s in raw.get("sources", []) if s.get("enabled", True)]

    raw_filters = raw.get("filters", {})
    filters = Filters(
        keywords=[str(k).lower() for k in raw_filters.get("keywords", [])],
        required_in_title=[str(k).lower() for k in raw_filters.get("required_in_title", [])],
        exclude=[str(k).lower() for k in raw_filters.get("exclude", [])],
    )

    settings = Settings(**raw.get("settings", {}))
    return Config(sources=sources, filters=filters, settings=settings)


def get_openai_api_key() -> Optional[str]:
    return os.environ.get("OPENAI_API_KEY")


def get_openai_base_url() -> str:
    return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")


def get_openai_model() -> str:
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
