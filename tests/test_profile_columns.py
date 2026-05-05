import pytest

from profile_columns import build_profile_columns, fullstack_span


def _payload_with_axes(**axes_overrides):
    axes = {
        "axis_backend": 0.9,
        "axis_frontend": 0.1,
        "axis_platform": 0.5,
        "axis_ai_data": 0.2,
        "axis_security_reliability": 0.6,
        "axis_product_ownership": 0.4,
    }
    axes.update(axes_overrides)
    return {
        "normalized_title": "Backend Engineer",
        "role_family": "backend",
        "seniority": "senior",
        "employment_type": "full_time",
        "work_mode": "remote",
        "location_scope": "US",
        "salary": {"salary_min": 150000, "salary_max": 200000,
                   "salary_currency": "USD", "salary_period": "annual"},
        "work_eligibility": {
            "work_auth_required": True,
            "sponsorship_available": False,
            "eligible_countries": ["US"],
            "eligible_regions": None,
        },
        "degree_required": 1,
        "summary": "x",
        "must_have_requirements": [],
        "preferred_requirements": [],
        "responsibilities": [],
        "skills": {"languages": [], "frameworks": [], "cloud": [],
                   "databases": [], "devops": [], "ai_ml": [],
                   "other_tools": [], "concepts": []},
        "experience_requirements": {"years_min": 5, "years_max": None,
                                    "level_signal": "senior",
                                    "years_min_hard": 5},
        "education_requirements": [],
        "domain_signals": [],
        "explicit_constraints": [],
        "extraction_confidence": 0.9,
        "evidence_snippets": [],
        "axes": axes,
        "profile_meta": {
            "schema_version": "2.0",
            "prompt_version": "2.0",
            "model": "gpt-4.1-nano",
            "generated_at": "2026-05-04T00:00:00+00:00",
        },
    }


@pytest.mark.parametrize("backend, frontend, expected", [
    (0.95, 0.05, 0.10),   # 2 * 0.05 = 0.10
    (0.80, 0.80, 1.00),   # 2 * 0.80 = 1.60, clamped to 1.00
    (0.50, 0.50, 1.00),   # 2 * 0.50 = 1.00
    (0.40, 0.50, 0.80),   # 2 * 0.40 = 0.80
    (0.00, 0.90, 0.00),   # 2 * 0.00 = 0.00
    (0.30, 0.30, 0.60),
])
def test_fullstack_span_formula(backend, frontend, expected):
    assert fullstack_span(backend, frontend) == expected


def test_build_columns_reads_axes_from_payload():
    payload = _payload_with_axes(axis_backend=0.95, axis_frontend=0.05)
    cols = build_profile_columns(
        payload, job_posting_id=1, content_hash="abc",
    )
    assert cols["axis_backend"] == 0.95
    assert cols["axis_frontend"] == 0.05
    assert cols["axis_platform"] == 0.5
    assert cols["axis_product_ownership"] == 0.4


def test_build_columns_computes_fullstack_span():
    payload = _payload_with_axes(axis_backend=0.95, axis_frontend=0.05)
    cols = build_profile_columns(
        payload, job_posting_id=1, content_hash="abc",
    )
    # 2 * min(0.95, 0.05) = 0.10
    assert cols["axis_fullstack_span"] == 0.10


def test_build_columns_passes_through_work_eligibility_directly():
    payload = _payload_with_axes()
    payload["work_eligibility"]["work_auth_required"] = True
    payload["work_eligibility"]["sponsorship_available"] = False
    payload["explicit_constraints"] = ["totally unrelated text"]  # was used by regex
    cols = build_profile_columns(
        payload, job_posting_id=1, content_hash="abc",
    )
    assert cols["work_auth_required"] == 1
    assert cols["sponsorship_available"] == 0


def test_build_columns_takes_degree_directly_from_llm():
    payload = _payload_with_axes()
    payload["degree_required"] = 2
    payload["education_requirements"] = []  # would have triggered the old fallback
    cols = build_profile_columns(
        payload, job_posting_id=1, content_hash="abc",
    )
    assert cols["degree_required"] == 2


def test_build_columns_keys_match_db_constants():
    """The dict returned must be a 1:1 superset for JOB_PROFILE_COLUMNS — every
    key must exist, no extras. Drift here breaks the upsert SQL."""
    import db
    payload = _payload_with_axes()
    cols = build_profile_columns(
        payload, job_posting_id=1, content_hash="abc",
    )
    assert set(cols.keys()) == set(db.JOB_PROFILE_COLUMNS) - {"is_active"}
