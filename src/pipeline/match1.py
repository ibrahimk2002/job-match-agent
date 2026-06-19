import math
import time
from typing import Any, Callable

from db import get_all_active_job_profiles

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


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def run_stage1_naive(
    user_axes: list[float],
    preferred_role: str | None,
    preferred_seniority: str | None,
    limit: int = 5,
) -> list[dict]:
    """Stage 1 without pgvector — Python cosine similarity over scalar columns."""
    profiles = get_all_active_job_profiles()
    scored = []
    for p in profiles:
        job_axes = [p.get(col) or 0.0 for col in _AXIS_COLS]
        sim = _cosine_similarity(user_axes, job_axes)
        role_bonus = _ROLE_BONUS if p.get("role_family") == preferred_role else 0.0
        seniority_bonus = _SENIORITY_BONUS if p.get("seniority") == preferred_seniority else 0.0
        scored.append({
            **p,
            "cosine_similarity": round(sim, 4),
            "match_score": round(sim + role_bonus + seniority_bonus, 4),
        })
    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:limit]
