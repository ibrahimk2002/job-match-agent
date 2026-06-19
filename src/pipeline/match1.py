import math
import time
from typing import Any, Callable

from db import get_all_active_job_profiles, get_user_by_email, get_active_user_profile, get_stage1_matches_pgvector

_AXIS_COLS = [
    "axis_backend",
    "axis_frontend",
    "axis_platform",
    "axis_ai_data",
    "axis_security_reliability",
    "axis_product_ownership",
]
_ROLE_BONUS = 0.10
_SENIORITY_BONUS = 0.05


def timed(fn: Callable, *args: Any, **kwargs: Any) -> tuple[Any, float]:
    """Return (result, elapsed_seconds) for fn(*args, **kwargs)."""
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - start


def _l2_similarity(a: list[float], b: list[float]) -> float:
    dist = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    return 1.0 / (1.0 + dist)


def get_user_axes_for_email(email: str) -> list[float]:
    user = get_user_by_email(email)
    if user is None:
        raise ValueError(f"No user found with email '{email}'")
    profile = get_active_user_profile(user["id"])
    if profile is None:
        raise ValueError(f"No active resume for '{email}'. Run 'ingest-resume' first.")
    return [profile.get(col) or 0.0 for col in _AXIS_COLS]


def run_stage1_pgvector(
    user_axes: list[float],
    preferred_role: str | None,
    preferred_seniority: str | None,
    limit: int = 5,
) -> list[dict]:
    return get_stage1_matches_pgvector(user_axes, preferred_role, preferred_seniority, limit)


def run_stage1_naive(
    user_axes: list[float],
    preferred_role: str | None,
    preferred_seniority: str | None,
    limit: int = 5,
) -> list[dict]:
    """Stage 1 without pgvector — Python L2 similarity over scalar columns."""
    profiles = get_all_active_job_profiles()
    scored = []
    for p in profiles:
        job_axes = [p.get(col) or 0.0 for col in _AXIS_COLS]
        sim = _l2_similarity(user_axes, job_axes)
        role_bonus = _ROLE_BONUS if p.get("role_family") == preferred_role else 0.0
        seniority_bonus = _SENIORITY_BONUS if p.get("seniority") == preferred_seniority else 0.0
        scored.append({
            **p,
            "l2_similarity": round(sim, 4),
            "match_score": round(sim + role_bonus + seniority_bonus, 4),
        })
    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:limit]
