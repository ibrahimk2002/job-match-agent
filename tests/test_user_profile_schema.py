def test_user_profile_models_are_importable():
    from config.user_profile import (
        ResumeSkills, WorkExperience, ResumeEducation,
        CareerPreferences, ResumeWorkAuth, ResumeExtractionResult, UserProfile,
    )
    from config.job_profile import Axes, EvidenceSnippet, ProfileMeta

    axes = Axes(
        axis_backend=0.7, axis_frontend=0.1, axis_platform=0.3,
        axis_ai_data=0.2, axis_security_reliability=0.3, axis_product_ownership=0.2,
    )
    assert axes.axis_backend == 0.7

    profile = UserProfile(
        meta=ProfileMeta(
            schema_version="1.0", prompt_version="1.0",
            model="gpt-4.1-nano", generated_at="2026-05-07T00:00:00+00:00",
        ),
        full_name="Jane Doe",
        total_years_experience=3.0,
        current_level="junior",
        primary_role_family="backend",
        axes=axes,
        skills=ResumeSkills(
            languages=["Python"], frameworks=["Django"], cloud=["AWS"],
            databases=["PostgreSQL"], devops=[], ai_ml=[], other_tools=[], concepts=[],
        ),
        work_experience=[
            WorkExperience(
                title="Backend Developer", company="Acme Inc",
                years=2.0, level_signal="junior",
                key_contributions=["Built REST APIs in Python"],
            )
        ],
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
        evidence_snippets=[EvidenceSnippet(field="primary_role_family", quote="built REST APIs")],
    )
    assert profile.full_name == "Jane Doe"
    assert profile.meta.schema_version == "1.0"
