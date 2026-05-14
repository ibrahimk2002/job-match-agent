from unittest.mock import MagicMock, patch


def test_extract_resume_profile_raises_on_null_output():
    """MalformedOutputError is raised when output_parsed is None."""
    from integrations import MalformedOutputError
    from integrations.openai_client import extract_resume_profile
    from models.user_profile import ResumeExtractionResult

    mock_response = MagicMock()
    mock_response.output_parsed = None
    mock_response.usage = MagicMock()

    mock_client = MagicMock()
    mock_client.responses.parse.return_value = mock_response

    import pytest
    with patch("integrations.openai_client.get_openai_client", return_value=mock_client):
        with pytest.raises(MalformedOutputError):
            extract_resume_profile(
                system_prompt="test prompt",
                resume_text="some resume text",
                model="gpt-4.1-nano",
                prompt_cache_key="test-key",
            )


def test_extract_resume_profile_returns_parsed_and_usage():
    """Returns (parsed, usage) tuple on success."""
    from integrations.openai_client import extract_resume_profile
    from models.user_profile import ResumeExtractionResult

    fake_parsed = MagicMock(spec=ResumeExtractionResult)
    mock_response = MagicMock()
    mock_response.output_parsed = fake_parsed
    mock_response.usage = MagicMock()

    mock_client = MagicMock()
    mock_client.responses.parse.return_value = mock_response

    with patch("integrations.openai_client.get_openai_client", return_value=mock_client):
        parsed, usage = extract_resume_profile(
            system_prompt="test",
            resume_text="Jane Doe, Python developer",
            model="gpt-4.1-nano",
            prompt_cache_key="test-key",
        )

    assert parsed is fake_parsed
    assert usage is mock_response.usage


import json
import pytest
from unittest.mock import MagicMock


def _make_fake_extraction_result():
    from models.user_profile import (
        ResumeExtractionResult, ResumeSkills,
        ResumeEducation, CareerPreferences, ResumeWorkAuth,
    )
    from models.job_profile import Axes, EvidenceSnippet
    return ResumeExtractionResult(
        full_name="Jane Doe",
        total_years_experience=3.0,
        current_level="junior",
        primary_role_family="backend",
        axes=Axes(
            axis_backend=0.7, axis_frontend=0.1, axis_platform=0.3,
            axis_ai_data=0.2, axis_security_reliability=0.3, axis_product_ownership=0.2,
        ),
        skills=ResumeSkills(
            languages=["Python"], frameworks=["Django"], cloud=["AWS"],
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


def test_extract_resume_saves_profile_with_denormalized_columns(temp_db, monkeypatch, tmp_path):
    import sqlite3
    import pipeline.extract_resume as extract_module

    fake_pdf = tmp_path / "resume.pdf"
    fake_pdf.write_bytes(b"%PDF fake content")

    fake_result = _make_fake_extraction_result()
    fake_usage = MagicMock()
    fake_usage.input_tokens = 500
    fake_usage.input_tokens_details = None

    monkeypatch.setattr(
        extract_module, "_extract_pdf_text",
        lambda path: "Jane Doe\nBackend Developer at Acme Inc\nPython, Django"
    )
    monkeypatch.setattr(
        extract_module, "_attempt_extraction",
        lambda text: (fake_result, fake_usage)
    )

    extract_module.extract_resume(str(fake_pdf), "jane@example.com")

    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE email = 'jane@example.com'"
        ).fetchone()
        assert user is not None

        profile = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ? AND is_active = 1",
            (user["id"],),
        ).fetchone()
        assert profile is not None
        assert profile["current_level"] == "junior"
        assert profile["primary_role_family"] == "backend"
        assert profile["axis_backend"] == pytest.approx(0.7)
        assert profile["axis_fullstack_span"] == pytest.approx(0.20)  # 2*min(0.7,0.1)
        assert profile["work_auth_canada"] == 1
        assert profile["work_auth_us"] == 0
        assert profile["degree_level"] == 1

        profile_json = json.loads(profile["profile_json"])
        assert profile_json["full_name"] == "Jane Doe"
        assert profile_json["extraction_confidence"] == pytest.approx(0.85)
    finally:
        conn.close()


def test_extract_resume_persists_personal_projects_in_profile_json(temp_db, monkeypatch, tmp_path):
    import sqlite3
    import pipeline.extract_resume as extract_module
    from models.user_profile import PersonalProject

    fake_pdf = tmp_path / "resume_projects.pdf"
    fake_pdf.write_bytes(b"%PDF fake content")

    project = PersonalProject(
        name="open-source-tool",
        description="A CLI tool for automating file organisation.",
        tech_stack=["Python", "Click", "SQLite"],
        key_contributions=["Designed plugin architecture", "Published on PyPI"],
        approximate_years=0.5,
    )
    base_result = _make_fake_extraction_result()
    fake_result = base_result.model_copy(update={"personal_projects": [project]})

    fake_usage = MagicMock()
    fake_usage.input_tokens = 300
    fake_usage.input_tokens_details = None

    monkeypatch.setattr(extract_module, "_extract_pdf_text", lambda path: "Jane Doe resume with projects")
    monkeypatch.setattr(extract_module, "_attempt_extraction", lambda text: (fake_result, fake_usage))

    extract_module.extract_resume(str(fake_pdf), "projects@example.com")

    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    try:
        user = conn.execute("SELECT id FROM users WHERE email = 'projects@example.com'").fetchone()
        assert user is not None
        row = conn.execute(
            "SELECT profile_json FROM user_profiles WHERE user_id = ? AND is_active = 1",
            (user["id"],),
        ).fetchone()
        assert row is not None
        profile_json = json.loads(row["profile_json"])
        projects = profile_json.get("personal_projects", [])
        assert len(projects) == 1
        assert projects[0]["name"] == "open-source-tool"
        assert "SQLite" in projects[0]["tech_stack"]
    finally:
        conn.close()


def test_extract_resume_skips_if_already_current(temp_db, monkeypatch, tmp_path, capsys):
    import pipeline.extract_resume as extract_module

    fake_pdf = tmp_path / "resume.pdf"
    resume_text = "Jane Doe\nBackend Developer"
    fake_pdf.write_bytes(b"%PDF fake")

    fake_result = _make_fake_extraction_result()
    fake_usage = MagicMock()
    fake_usage.input_tokens = 100
    fake_usage.input_tokens_details = None

    monkeypatch.setattr(extract_module, "_extract_pdf_text", lambda path: resume_text)
    monkeypatch.setattr(extract_module, "_attempt_extraction", lambda text: (fake_result, fake_usage))

    # First extraction
    extract_module.extract_resume(str(fake_pdf), "jane@example.com")

    # Second extraction with same content — should skip
    attempt_count = {"n": 0}
    original_attempt = extract_module._attempt_extraction
    def counting_attempt(text):
        attempt_count["n"] += 1
        return original_attempt(text)
    monkeypatch.setattr(extract_module, "_attempt_extraction", counting_attempt)

    extract_module.extract_resume(str(fake_pdf), "jane@example.com")
    captured = capsys.readouterr()
    assert "already up to date" in captured.out
    assert attempt_count["n"] == 0
