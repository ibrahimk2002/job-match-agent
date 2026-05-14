import json

from models.user_profile import UserProfile


USER_PROFILE_COLUMNS = [
    "full_name",
    "total_years_experience",
    "current_level",
    "primary_role_family",
    "axis_backend",
    "axis_frontend",
    "axis_platform",
    "axis_ai_data",
    "axis_security_reliability",
    "axis_product_ownership",
    "axis_fullstack_span",
    "skills_languages",
    "skills_frameworks",
    "skills_cloud",
    "desired_role_families",
    "desired_seniority",
    "desired_work_modes",
    "desired_locations",
    "desired_salary_min",
    "desired_salary_max",
    "desired_salary_currency",
    "work_auth_canada",
    "work_auth_us",
    "sponsorship_needed",
    "degree_level",
]


def build_profile_columns(profile: UserProfile) -> dict:
    axes = profile.axes
    backend = axes.axis_backend
    frontend = axes.axis_frontend
    return {
        "full_name": profile.full_name,
        "total_years_experience": profile.total_years_experience,
        "current_level": profile.current_level,
        "primary_role_family": profile.primary_role_family,
        "axis_backend": backend,
        "axis_frontend": frontend,
        "axis_platform": axes.axis_platform,
        "axis_ai_data": axes.axis_ai_data,
        "axis_security_reliability": axes.axis_security_reliability,
        "axis_product_ownership": axes.axis_product_ownership,
        "axis_fullstack_span": round(min(2 * min(backend, frontend), 1.0), 2),
        "skills_languages": json.dumps(profile.skills.languages),
        "skills_frameworks": json.dumps(profile.skills.frameworks),
        "skills_cloud": json.dumps(profile.skills.cloud),
        "desired_role_families": json.dumps(profile.preferences.desired_role_families),
        "desired_seniority": profile.preferences.desired_seniority,
        "desired_work_modes": json.dumps(profile.preferences.desired_work_modes),
        "desired_locations": json.dumps(profile.preferences.desired_locations),
        "desired_salary_min": profile.preferences.desired_salary_min,
        "desired_salary_max": profile.preferences.desired_salary_max,
        "desired_salary_currency": profile.preferences.desired_salary_currency,
        "work_auth_canada": int(profile.work_auth.canada),
        "work_auth_us": int(profile.work_auth.us),
        "sponsorship_needed": (
            int(profile.work_auth.sponsorship_needed)
            if profile.work_auth.sponsorship_needed is not None else None
        ),
        "degree_level": profile.education.degree_level,
    }
