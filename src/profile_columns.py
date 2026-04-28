import json
import re
from typing import Any


def default_axes_for_role_family(role_family: str | None) -> dict[str, float]:
    presets = {
        "backend":    {"backend": 1.0,  "frontend": 0.1,  "platform_cloud": 0.45, "ai_data": 0.1,  "security_reliability": 0.35, "product_sense": 0.35, "fullstack_span": 0.20},
        "frontend":   {"backend": 0.1,  "frontend": 1.0,  "platform_cloud": 0.10, "ai_data": 0.05, "security_reliability": 0.30, "product_sense": 0.50, "fullstack_span": 0.20},
        "full_stack": {"backend": 0.75, "frontend": 0.75, "platform_cloud": 0.20, "ai_data": 0.1,  "security_reliability": 0.45, "product_sense": 0.45, "fullstack_span": 1.00},
        "data":       {"backend": 0.25, "frontend": 0.0,  "platform_cloud": 0.35, "ai_data": 1.0,  "security_reliability": 0.35, "product_sense": 0.30, "fullstack_span": 0.10},
        "ml":         {"backend": 0.25, "frontend": 0.0,  "platform_cloud": 0.30, "ai_data": 1.0,  "security_reliability": 0.40, "product_sense": 0.30, "fullstack_span": 0.15},
        "devops":     {"backend": 0.35, "frontend": 0.0,  "platform_cloud": 1.00, "ai_data": 0.05, "security_reliability": 0.45, "product_sense": 0.35, "fullstack_span": 0.30},
        "qa":         {"backend": 0.2,  "frontend": 0.2,  "platform_cloud": 0.20, "ai_data": 0.0,  "security_reliability": 0.30, "product_sense": 0.75, "fullstack_span": 0.35},
        "mobile":     {"backend": 0.2,  "frontend": 0.65, "platform_cloud": 0.10, "ai_data": 0.05, "security_reliability": 0.35, "product_sense": 0.40, "fullstack_span": 0.25},
        "unknown":    {"backend": 0.0,  "frontend": 0.0,  "platform_cloud": 0.00, "ai_data": 0.0,  "security_reliability": 0.25, "product_sense": 0.25, "fullstack_span": 0.00},
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
    explicit_constraints = profile_payload.get("explicit_constraints") or []
    education_requirements = profile_payload.get("education_requirements") or []

    role_family = profile_payload.get("role_family") or "unknown"
    seniority = profile_payload.get("seniority") or "unknown"
    employment_type = profile_payload.get("employment_type") or "unknown"
    work_mode = profile_payload.get("work_mode") or "unknown"

    axes = default_axes_for_role_family(role_family)

    salary = profile_payload.get("salary") or {}

    work_eligibility = profile_payload.get("work_eligibility") or {}
    model_work_auth = work_eligibility.get("work_auth_required")
    model_sponsorship = work_eligibility.get("sponsorship_available")

    if model_work_auth is None and model_sponsorship is None:
        work_auth_required, sponsorship_available = infer_work_auth_flags(explicit_constraints)
    else:
        work_auth_required = _bool_to_sqlite(model_work_auth)
        sponsorship_available = _bool_to_sqlite(model_sponsorship)

    model_degree = profile_payload.get("degree_required")
    degree_required = (
        model_degree
        if model_degree is not None
        else bool_from_requirement_list(education_requirements)
    )

    eligible_countries = work_eligibility.get("eligible_countries")
    eligible_regions = work_eligibility.get("eligible_regions")

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
        "seniority": seniority,
        "employment_type": employment_type,
        "work_mode": work_mode,
        "location_scope": profile_payload.get("location_scope"),
        "work_auth_required": work_auth_required if work_auth_required is not None else 0,
        "sponsorship_available": sponsorship_available,
        "degree_required": degree_required,
        "years_min_soft": experience.get("years_min"),
        "years_min_hard": experience.get("years_min_hard"),
        "salary_min": salary.get("salary_min"),
        "salary_max": salary.get("salary_max"),
        "salary_currency": salary.get("salary_currency"),
        "salary_period": salary.get("salary_period"),
        "salary_tier": infer_salary_tier(seniority),
        "axis_backend": axes["backend"],
        "axis_frontend": axes["frontend"],
        "axis_platform_cloud": axes["platform_cloud"],
        "axis_ai_data": axes["ai_data"],
        "axis_security_reliability": axes["security_reliability"],
        "axis_product_sense": axes["product_sense"],
        "axis_fullstack_span": axes["fullstack_span"],
        "eligible_countries_json": json.dumps(eligible_countries) if eligible_countries else None,
        "eligible_regions_json": json.dumps(eligible_regions) if eligible_regions else None,
    }
