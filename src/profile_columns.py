import json
import re
from typing import Any


def default_axes_for_role_family(role_family: str | None) -> dict[str, float]:
    presets = {
        "backend": {"backend": 1.0, "frontend": 0.1, "platform": 0.45, "ai_data": 0.1, "ownership": 0.35, "collaboration": 0.35},
        "frontend": {"backend": 0.1, "frontend": 1.0, "platform": 0.1, "ai_data": 0.05, "ownership": 0.3, "collaboration": 0.5},
        "full_stack": {"backend": 0.75, "frontend": 0.75, "platform": 0.2, "ai_data": 0.1, "ownership": 0.45, "collaboration": 0.45},
        "data": {"backend": 0.25, "frontend": 0.0, "platform": 0.35, "ai_data": 1.0, "ownership": 0.35, "collaboration": 0.3},
        "ml": {"backend": 0.25, "frontend": 0.0, "platform": 0.3, "ai_data": 1.0, "ownership": 0.4, "collaboration": 0.3},
        "devops": {"backend": 0.35, "frontend": 0.0, "platform": 1.0, "ai_data": 0.05, "ownership": 0.45, "collaboration": 0.35},
        "qa": {"backend": 0.2, "frontend": 0.2, "platform": 0.2, "ai_data": 0.0, "ownership": 0.3, "collaboration": 0.75},
        "mobile": {"backend": 0.2, "frontend": 0.65, "platform": 0.1, "ai_data": 0.05, "ownership": 0.35, "collaboration": 0.4},
        "unknown": {"backend": 0.0, "frontend": 0.0, "platform": 0.0, "ai_data": 0.0, "ownership": 0.25, "collaboration": 0.25},
    }
    return presets.get(role_family or "unknown", presets["unknown"])


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


def bool_from_requirement_list(requirements: list[Any] | None) -> int | None:
    if requirements is None:
        return None
    return 1 if len(requirements) > 0 else 0


def infer_work_auth_flags(explicit_constraints: list[Any] | None) -> tuple[int | None, int | None]:
    if not explicit_constraints:
        return None, None

    joined = " ".join(str(item).lower() for item in explicit_constraints)
    sponsorship_available = None
    work_auth_required = None

    if "sponsorship" in joined:
        sponsorship_available = 0 if re.search(r"no\s+sponsorship|without\s+sponsorship|unable\s+to\s+sponsor", joined) else 1
    if re.search(r"authorized to work|work authorization|required to work|eligible to work", joined):
        work_auth_required = 1

    return work_auth_required, sponsorship_available


def build_profile_columns(
    profile_payload: dict[str, Any],
    *,
    job_posting_id: int,
    content_hash: str,
    extracted_at: str | None = None,
) -> dict[str, Any]:
    profile_meta = profile_payload.get("profile_meta") or {}
    experience = profile_payload.get("experience_requirements") or {}
    explicit_constraints = profile_payload.get("explicit_constraints") or []
    education_requirements = profile_payload.get("education_requirements") or []

    role_family = profile_payload.get("role_family") or "unknown"
    seniority = profile_payload.get("seniority") or "unknown"
    employment_type = profile_payload.get("employment_type") or "unknown"
    work_mode = profile_payload.get("work_mode") or "unknown"

    axes = default_axes_for_role_family(role_family)
    work_auth_required, sponsorship_available = infer_work_auth_flags(explicit_constraints)

    return {
        "job_posting_id": job_posting_id,
        "content_hash": content_hash,
        "schema_version": profile_meta.get("schema_version") or "1.0",
        "prompt_version": profile_meta.get("prompt_version") or "unknown",
        "model_version": profile_meta.get("model") or "unknown",
        "extracted_at": extracted_at or profile_meta.get("generated_at"),
        "extraction_confidence": profile_payload.get("extraction_confidence") or 0.5,
        "profile_json": json.dumps(profile_payload, sort_keys=True),
        "normalized_title": profile_payload.get("normalized_title") or "",
        "role_family": role_family,
        "role_subtype": profile_payload.get("role_subtype"),
        "seniority": seniority,
        "employment_type": employment_type,
        "work_mode": work_mode,
        "location_scope": profile_payload.get("location_scope"),
        "work_auth_required": work_auth_required,
        "sponsorship_available": sponsorship_available,
        "degree_required": bool_from_requirement_list(education_requirements),
        "years_min_soft": experience.get("years_min"),
        "years_min_hard": None,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "salary_period": None,
        "salary_tier": infer_salary_tier(seniority),
        "axis_backend": axes["backend"],
        "axis_frontend": axes["frontend"],
        "axis_platform": axes["platform"],
        "axis_ai_data": axes["ai_data"],
        "axis_ownership": axes["ownership"],
        "axis_collaboration": axes["collaboration"],
        "eligible_countries_json": None,
        "eligible_regions_json": None,
    }
