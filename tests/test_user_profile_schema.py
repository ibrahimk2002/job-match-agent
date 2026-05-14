import pytest


def test_personal_project_accepts_null_duration():
    from models.user_profile import PersonalProject
    p = PersonalProject(
        name="job-match-agent",
        description="AI-powered job matching system using LLMs.",
        tech_stack=["Python", "SQLite", "OpenAI"],
        key_contributions=["Built ingestion pipeline", "Designed schema"],
        approximate_years=None,
    )
    assert p.approximate_years is None


def test_personal_project_requires_name_and_description():
    from models.user_profile import PersonalProject
    with pytest.raises(Exception):
        PersonalProject(
            description="A project.",
            tech_stack=["Python"],
            key_contributions=["Did stuff"],
            approximate_years=None,
        )
    with pytest.raises(Exception):
        PersonalProject(
            name="MyProject",
            tech_stack=["Python"],
            key_contributions=["Did stuff"],
            approximate_years=None,
        )


def test_resume_extraction_result_personal_projects_defaults_empty():
    from models.user_profile import (
        ResumeExtractionResult, ResumeSkills, ResumeEducation,
        CareerPreferences, ResumeWorkAuth,
    )
    from models.job_profile import Axes
    result = ResumeExtractionResult(
        full_name="Test User",
        total_years_experience=2.0,
        current_level="junior",
        primary_role_family="backend",
        axes=Axes(
            axis_backend=0.4, axis_frontend=0.1, axis_platform=0.1,
            axis_ai_data=0.1, axis_security_reliability=0.1, axis_product_ownership=0.1,
        ),
        skills=ResumeSkills(
            languages=["Python"], frameworks=[], cloud=[],
            databases=[], devops=[], ai_ml=[], other_tools=[], concepts=[],
        ),
        work_experience=[],
        education=ResumeEducation(degree_level=1, fields=["CS"]),
        preferences=CareerPreferences(
            desired_roles=[], desired_role_families=["backend"],
            desired_seniority="any", desired_work_modes=[], desired_locations=[],
            desired_salary_min=None, desired_salary_max=None, desired_salary_currency="CAD",
        ),
        work_auth=ResumeWorkAuth(canada=True, us=False, sponsorship_needed=None),
        extraction_confidence=0.8,
        evidence_snippets=[],
    )
    assert result.personal_projects == []


def test_user_profile_personal_projects_round_trips_model_dump():
    from models.user_profile import (
        UserProfile, ResumeSkills, ResumeEducation,
        CareerPreferences, ResumeWorkAuth, PersonalProject,
    )
    from models.job_profile import Axes, ProfileMeta
    project = PersonalProject(
        name="cli-tool",
        description="A command-line task manager written in Python.",
        tech_stack=["Python", "Click"],
        key_contributions=["Implemented CRUD commands", "Added SQLite backend"],
        approximate_years=0.5,
    )
    profile = UserProfile(
        meta=ProfileMeta(
            schema_version="1.1", prompt_version="2.1",
            model="gpt-4.1-nano", generated_at="2026-05-11T00:00:00+00:00",
        ),
        full_name="Dev User",
        total_years_experience=1.0,
        current_level="junior",
        primary_role_family="backend",
        axes=Axes(
            axis_backend=0.3, axis_frontend=0.0, axis_platform=0.0,
            axis_ai_data=0.0, axis_security_reliability=0.0, axis_product_ownership=0.0,
        ),
        skills=ResumeSkills(
            languages=["Python"], frameworks=[], cloud=[],
            databases=[], devops=[], ai_ml=[], other_tools=[], concepts=[],
        ),
        work_experience=[],
        personal_projects=[project],
        education=ResumeEducation(degree_level=1, fields=["CS"]),
        preferences=CareerPreferences(
            desired_roles=[], desired_role_families=["backend"],
            desired_seniority="any", desired_work_modes=[], desired_locations=[],
            desired_salary_min=None, desired_salary_max=None, desired_salary_currency="CAD",
        ),
        work_auth=ResumeWorkAuth(canada=True, us=False, sponsorship_needed=None),
        extraction_confidence=0.75,
        evidence_snippets=[],
    )
    dumped = profile.model_dump()
    assert len(dumped["personal_projects"]) == 1
    p = dumped["personal_projects"][0]
    assert p["name"] == "cli-tool"
    assert p["tech_stack"] == ["Python", "Click"]
    assert p["approximate_years"] == pytest.approx(0.5)


def test_user_profile_models_are_importable():
    from models.user_profile import (
        ResumeSkills, WorkExperience, ResumeEducation,
        CareerPreferences, ResumeWorkAuth, ResumeExtractionResult, UserProfile,
    )
    from models.job_profile import Axes, EvidenceSnippet, ProfileMeta

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
