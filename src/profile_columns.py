import json
from typing import Any


def fullstack_span(axis_backend: float, axis_frontend: float) -> float:
    """Derived axis from AXIS_MEASURE_SKILL.md: 2 * min(backend, frontend), clamped."""
    return round(min(2 * min(axis_backend, axis_frontend), 1.0), 2)


def infer_salary_tier(seniority: str | None) -> int | None:
    if seniority in {"intern", "new_grad"}:
        return 1
    if seniority in {"junior", "mid"}:
        return 2
    if seniority == "senior":
        return 3
    if seniority in {"staff", "principal"}:
        return 4
    return None


def _bool_to_sqlite(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def build_profile_columns(
    profile_payload: dict[str, Any],
    *,
    job_posting_id: int,
    content_hash: str,
    extracted_at: str | None = None,
) -> dict[str, Any]:
    profile_meta = profile_payload.get("profile_meta") or {}
    experience = profile_payload.get("experience_requirements") or {}

    role_family = profile_payload.get("role_family") or "unknown"
    seniority = profile_payload.get("seniority") or "unknown"
    employment_type = profile_payload.get("employment_type") or "unknown"
    work_mode = profile_payload.get("work_mode") or "unknown"

    axes = profile_payload["axes"]  # required field on JobProfile; KeyError = contract violation

    salary = profile_payload.get("salary") or {}
    work_eligibility = profile_payload.get("work_eligibility") or {}

    eligible_countries = work_eligibility.get("eligible_countries")
    eligible_regions = work_eligibility.get("eligible_regions")

    return {
        "job_posting_id": job_posting_id,
        "content_hash": content_hash,
        "schema_version": profile_meta.get("schema_version") or "2.0",
        "prompt_version": profile_meta.get("prompt_version") or "unknown",
        "model_version": profile_meta.get("model") or "unknown",
        "extracted_at": extracted_at or profile_meta.get("generated_at"),
        "extraction_confidence": profile_payload.get("extraction_confidence") or 0.5,
        "profile_json": json.dumps(profile_payload, sort_keys=True),
        "normalized_title": profile_payload.get("normalized_title") or "",
        "role_family": role_family,
        "seniority": seniority,
        "employment_type": employment_type,
        "work_mode": work_mode,
        "location_scope": profile_payload.get("location_scope"),
        "work_auth_required": _bool_to_sqlite(work_eligibility.get("work_auth_required")),
        "sponsorship_available": _bool_to_sqlite(work_eligibility.get("sponsorship_available")),
        "degree_required": profile_payload.get("degree_required"),
        "years_min_soft": experience.get("years_min"),
        "years_min_hard": experience.get("years_min_hard"),
        "salary_min": salary.get("salary_min"),
        "salary_max": salary.get("salary_max"),
        "salary_currency": salary.get("salary_currency"),
        "salary_period": salary.get("salary_period"),
        "salary_tier": infer_salary_tier(seniority),
        "axis_backend": axes["axis_backend"],
        "axis_frontend": axes["axis_frontend"],
        "axis_platform": axes["axis_platform"],
        "axis_ai_data": axes["axis_ai_data"],
        "axis_security_reliability": axes["axis_security_reliability"],
        "axis_product_ownership": axes["axis_product_ownership"],
        "axis_fullstack_span": fullstack_span(axes["axis_backend"], axes["axis_frontend"]),
        "eligible_countries_json": json.dumps(eligible_countries) if eligible_countries else None,
        "eligible_regions_json": json.dumps(eligible_regions) if eligible_regions else None,
    }
