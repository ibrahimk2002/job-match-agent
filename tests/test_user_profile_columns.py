import pytest


def _make_profile():
    from models.user_profile import (
        UserProfile, ResumeSkills,
        ResumeEducation, CareerPreferences, ResumeWorkAuth,
    )
    from models.job_profile import ProfileMeta, Axes
    return UserProfile(
        meta=ProfileMeta(
            schema_version="1.0", prompt_version="1.0",
            model="gpt-4.1-nano", generated_at="2026-05-07T00:00:00+00:00",
        ),
        full_name="Jane Doe",
        total_years_experience=3.0,
        current_level="junior",
        primary_role_family="backend",
        axes=Axes(
            axis_backend=0.7, axis_frontend=0.1, axis_platform=0.3,
            axis_ai_data=0.2, axis_security_reliability=0.3, axis_product_ownership=0.2,
        ),
        skills=ResumeSkills(
            languages=["Python", "Go"], frameworks=["Django"], cloud=["AWS"],
            databases=["PostgreSQL"], devops=[], ai_ml=[], other_tools=[], concepts=[],
        ),
        work_experience=[],
        education=ResumeEducation(degree_level=1, fields=["Computer Science"]),
        preferences=CareerPreferences(
            desired_roles=["Backend Engineer"],
            desired_role_families=["backend"],
            desired_seniority="mid",
            desired_work_modes=["remote"],
            desired_locations=["Toronto"],
            desired_salary_min=80000,
            desired_salary_max=120000,
            desired_salary_currency="CAD",
        ),
        work_auth=ResumeWorkAuth(canada=True, us=False, sponsorship_needed=None),
        extraction_confidence=0.85,
        evidence_snippets=[],
    )


def test_build_columns_keys_match_user_profile_columns():
    from user_profile_columns import build_profile_columns, USER_PROFILE_COLUMNS
    profile = _make_profile()
    cols = build_profile_columns(profile)
    assert set(cols.keys()) == set(USER_PROFILE_COLUMNS)


def test_fullstack_span_derived_correctly():
    from user_profile_columns import build_profile_columns
    profile = _make_profile()
    # axis_backend=0.7, axis_frontend=0.1 → span = round(min(2*0.1, 1.0), 2) = 0.20
    cols = build_profile_columns(profile)
    assert cols["axis_fullstack_span"] == pytest.approx(0.20)


def test_skills_serialized_as_json():
    import json
    from user_profile_columns import build_profile_columns
    profile = _make_profile()
    cols = build_profile_columns(profile)
    assert json.loads(cols["skills_languages"]) == ["Python", "Go"]
    assert json.loads(cols["skills_frameworks"]) == ["Django"]


def test_work_auth_converted_to_int():
    from user_profile_columns import build_profile_columns
    profile = _make_profile()
    cols = build_profile_columns(profile)
    assert cols["work_auth_canada"] == 1
    assert cols["work_auth_us"] == 0
    assert cols["sponsorship_needed"] is None
