"""Runtime configuration. Every knob is an environment variable so Docker Compose
and local runs share one code path."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://aeo:aeo@localhost:5432/aeo")
    # Base URL the worker uses to reach its own demo sites (served at /demo-sites)
    demo_base_url: str = os.getenv("DEMO_BASE_URL", "http://localhost:8000/demo-sites")
    seed_on_start: bool = os.getenv("SEED_ON_START", "true").lower() == "true"

    # NLP backends: "auto" tries transformers then falls back, "lite" never loads models
    nlp_mode: str = os.getenv("NLP_MODE", "auto")
    sentiment_model: str = os.getenv("SENTIMENT_MODEL", "ProsusAI/finbert")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
    embedding_dim: int = 768

    # Headless rendering: "auto" uses Playwright when importable, else XHR interception emulation
    render_mode: str = os.getenv("RENDER_MODE", "auto")

    # Temporal graph parameters
    half_life_days: dict = field(default_factory=lambda: {
        "institutional_filing": None,      # ground truth does not decay while valid
        "institutional_web": None,
        "press": _f("HALF_LIFE_PRESS", 180),
        "retail_forum": _f("HALF_LIFE_FORUM", 90),
    })
    authority: dict = field(default_factory=lambda: {
        "institutional_filing": 1.0,
        "institutional_web": 0.9,
        "press": 0.5,
        "retail_forum": 0.15,
    })
    supersession_penalty: float = _f("SUPERSESSION_PENALTY", 0.9)
    value_tolerance: float = _f("VALUE_TOLERANCE", 0.05)

    severance_threshold: float = _f("SEVERANCE_THRESHOLD", 0.75)
    zero_vector_min_tokens: int = int(os.getenv("ZERO_VECTOR_MIN_TOKENS", "60"))

    # Namespace vector priorities emitted in the Comparative Markdown Matrix
    legacy_weight: float = _f("LEGACY_VECTOR_WEIGHT", 0.1)
    active_weight: float = _f("ACTIVE_VECTOR_WEIGHT", 1.0)


settings = Settings()

INSTITUTIONAL_SOURCES = {"institutional_filing", "institutional_web"}
