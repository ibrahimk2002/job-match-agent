import pytest
from pydantic import ValidationError

from models.job_profile import Axes, ExtractionResult, JobProfile


def test_axes_accepts_six_primary_axis_fields():
    axes = Axes(
        axis_backend=0.95,
        axis_frontend=0.05,
        axis_platform=0.75,
        axis_ai_data=0.25,
        axis_security_reliability=0.70,
        axis_product_ownership=0.35,
    )
    assert axes.axis_backend == 0.95
    assert axes.axis_product_ownership == 0.35


def test_axes_rejects_missing_field():
    with pytest.raises(ValidationError):
        Axes(  # missing axis_product_ownership
            axis_backend=0.5,
            axis_frontend=0.5,
            axis_platform=0.5,
            axis_ai_data=0.5,
            axis_security_reliability=0.5,
        )


def test_axes_does_not_have_fullstack_span_field():
    """fullstack_span is computed downstream; it must not be on the Pydantic model
    because we don't want the LLM to emit it."""
    assert "axis_fullstack_span" not in Axes.model_fields
    assert "fullstack_span" not in Axes.model_fields


def _valid_extraction_payload():
    return {
        "normalized_title": "Senior Backend Engineer",
        "role_family": "backend",
        "seniority": "senior",
        "employment_type": "full_time",
        "work_mode": "remote",
        "location_scope": "United States",
        "salary": {},
        "work_eligibility": {},
        "degree_required": 1,
        "summary": "Build scalable APIs.",
        "must_have_requirements": ["5+ years backend"],
        "preferred_requirements": [],
        "responsibilities": ["Design APIs"],
        "skills": {
            "languages": ["Python"], "frameworks": [], "cloud": [],
            "databases": [], "devops": [], "ai_ml": [],
            "other_tools": [], "concepts": [],
        },
        "experience_requirements": {
            "years_min": 5, "years_max": None, "level_signal": "senior",
            "years_min_hard": 5,
        },
        "education_requirements": [],
        "domain_signals": [],
        "explicit_constraints": [],
        "extraction_confidence": 0.85,
        "evidence_snippets": [],
        "axes": {
            "axis_backend": 0.9,
            "axis_frontend": 0.1,
            "axis_platform": 0.5,
            "axis_ai_data": 0.2,
            "axis_security_reliability": 0.6,
            "axis_product_ownership": 0.4,
        },
    }


def test_extraction_result_requires_axes():
    payload = _valid_extraction_payload()
    del payload["axes"]
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(payload)


def test_extraction_result_accepts_axes():
    result = ExtractionResult.model_validate(_valid_extraction_payload())
    assert result.axes.axis_backend == 0.9
    assert result.axes.axis_product_ownership == 0.4


def test_job_profile_carries_axes_through():
    payload = _valid_extraction_payload()
    profile_payload = {
        **payload,
        "job_id": "src-123",
        "profile_meta": {
            "schema_version": "2.0",
            "prompt_version": "2.0",
            "model": "gpt-4.1-nano",
            "generated_at": "2026-05-04T00:00:00+00:00",
        },
    }
    profile = JobProfile.model_validate(profile_payload)
    assert profile.axes.axis_backend == 0.9
