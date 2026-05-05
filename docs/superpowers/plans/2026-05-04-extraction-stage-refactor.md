# Extraction Stage Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Refactor the extraction stage so the LLM produces axis scores (no presets), the schemas align across `ExtractionResult` ↔ `JobProfile` ↔ `job_profiles` table, and `responses.parse()` calls are structured for prompt caching with `prompt_cache_key`.

**Architecture:** Single-call extraction via `client.responses.parse()` using an input array (`role: "system"` + user `<job_description>`). The `prompts/extraction.txt` static prefix carries the full axis rubric (verbatim from `docs/AXIS_MEASURE_SKILL.md`) plus a Ford anchor — large enough to clear OpenAI's 1024-token auto-cache floor. `profile_columns.py` becomes a pure projection that maps payload fields → DB columns and computes only mechanically derived fields (`axis_fullstack_span`, `salary_tier`).

**Tech Stack:** Python 3.11+, Pydantic v2, OpenAI SDK 2.x (`responses.parse` + `prompt_cache_key`), SQLite, pytest.

**Spec:** `docs/superpowers/specs/2026-05-04-extraction-stage-refactor-design.md`

**Issue:** [#13](https://github.com/ibrahimk2002/job-match-agent/issues/13)

---

## File map

**New files:**
- `migrations/003_rename_axes.sql` — column renames
- `tests/conftest.py` — sys.path setup + temp-DB fixture
- `tests/test_migrations.py` — verifies migration application
- `tests/test_job_profile_schema.py` — Pydantic model tests
- `tests/test_profile_columns.py` — projection-layer tests

**Modified files:**
- `src/db.py` — `JOB_PROFILE_COLUMNS` axis keys
- `config/job_profile.py` — add `Axes`; add `axes` to `ExtractionResult` and `JobProfile`
- `src/profile_columns.py` — drop fallbacks, add `fullstack_span`, project axes from payload
- `src/prompts/extraction.txt` — bump `prompt_version: 2.0`, append axis rubric + Ford anchor
- `docs/AXIS_MEASURE_SKILL.md` — sync note
- `src/integrations/openai_client.py` — `extract_job_profile` rewrite
- `src/pipeline/extract.py` — `SCHEMA_VERSION = "2.0"`, module-level prompt load, retry/truncate/skip handling, usage accumulation, run summary

**Out of scope (explicit deferrals from the spec):** language detection, async extraction, mocked LLM tests for `extract.py` / `openai_client.py`, embeddings.

---

### Task 1: Test infrastructure — `conftest.py` with temp-DB fixture

The codebase currently has no tests. Set up minimal infrastructure so subsequent tasks can TDD against a real SQLite DB.

**Files:**
- Create: `tests/conftest.py`

- [x] **Step 1: Write the conftest**

```python
# tests/conftest.py
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# Order matters: src/ must come first so `import db` resolves to src/db.py,
# not anything else. ROOT is needed for `from config.job_profile import ...`.
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def temp_db(monkeypatch):
    """Yields a path to a fresh SQLite DB with all migrations applied."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    import db as db_module
    monkeypatch.setattr(db_module, "_DB_PATH", path)
    db_module.init_db()

    yield path

    try:
        os.remove(path)
    except OSError:
        pass
```

- [x] **Step 2: Sanity-check the fixture loads**

Run: `cd /home/ibrahim/Documents/job-match-agent && pytest --collect-only 2>&1 | tail -5`
Expected: `no tests ran` (or similar) — fixture file imports cleanly with no errors.

- [x] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add conftest with temp-DB fixture for upcoming extraction tests"
```

---

### Task 2: `Axes` Pydantic model

Standalone model. No coupling to `ExtractionResult` yet — add separately so the test fails for the right reason.

**Files:**
- Modify: `config/job_profile.py`
- Create: `tests/test_job_profile_schema.py`

- [x] **Step 1: Write the failing test**

```python
# tests/test_job_profile_schema.py
import pytest
from pydantic import ValidationError

from config.job_profile import Axes


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
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_job_profile_schema.py -v`
Expected: FAIL with `ImportError: cannot import name 'Axes' from 'config.job_profile'`

- [x] **Step 3: Add the `Axes` model**

Edit `config/job_profile.py`. After the existing `ExperienceRequirements` class and before `EvidenceSnippet`, insert:

```python
class Axes(BaseModel):
    axis_backend: float
    axis_frontend: float
    axis_platform: float
    axis_ai_data: float
    axis_security_reliability: float
    axis_product_ownership: float
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_job_profile_schema.py -v`
Expected: 3 passed.

- [x] **Step 5: Commit**

```bash
git add config/job_profile.py tests/test_job_profile_schema.py
git commit -m "feat: add Axes pydantic model with six primary axes"
```

---

### Task 3: Add `axes` field to `ExtractionResult` and `JobProfile`

**Files:**
- Modify: `config/job_profile.py`
- Modify: `tests/test_job_profile_schema.py`

- [x] **Step 1: Write the failing test**

Append to `tests/test_job_profile_schema.py`:

```python
from config.job_profile import ExtractionResult, JobProfile


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
```

- [x] **Step 2: Run test to verify failures**

Run: `pytest tests/test_job_profile_schema.py -v`
Expected: 3 new tests FAIL because `axes` is not yet on `ExtractionResult`/`JobProfile`.

- [x] **Step 3: Add `axes` to both models**

Edit `config/job_profile.py`. In the `JobProfile` class, after `evidence_snippets: list[EvidenceSnippet]` and before `profile_meta: ProfileMeta`, insert:

```python
    axes: Axes
```

In the `ExtractionResult` class, after `evidence_snippets: list[EvidenceSnippet]` (the last existing line of the class), append:

```python
    axes: Axes
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_job_profile_schema.py -v`
Expected: 6 passed.

- [x] **Step 5: Commit**

```bash
git add config/job_profile.py tests/test_job_profile_schema.py
git commit -m "feat: add axes field to ExtractionResult and JobProfile"
```

---

### Task 4: Atomic axis rename — migration 003 + `JOB_PROFILE_COLUMNS` + `profile_columns.py` keys

This is one atomic step because partial renames break the upsert (the dict from `build_profile_columns` must produce keys that match `JOB_PROFILE_COLUMNS` exactly). Axis source-of-truth is **still** the presets after this task — switching to LLM-payload comes in Task 5.

**Files:**
- Create: `migrations/003_rename_axes.sql`
- Modify: `src/db.py` (lines around 53-57 in `JOB_PROFILE_COLUMNS`)
- Modify: `src/profile_columns.py` (preset dict keys + the return-dict keys)
- Create: `tests/test_migrations.py`

- [x] **Step 1: Write the failing migration test**

```python
# tests/test_migrations.py
def _column_names(temp_db_path, table):
    import sqlite3
    conn = sqlite3.connect(temp_db_path)
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [r[1] for r in rows]
    finally:
        conn.close()


def test_axis_columns_use_canonical_names(temp_db):
    cols = _column_names(temp_db, "job_profiles")
    assert "axis_platform" in cols
    assert "axis_product_ownership" in cols
    assert "axis_platform_cloud" not in cols
    assert "axis_product_sense" not in cols


def test_axis_fullstack_span_column_still_exists(temp_db):
    cols = _column_names(temp_db, "job_profiles")
    assert "axis_fullstack_span" in cols
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_migrations.py -v`
Expected: `test_axis_columns_use_canonical_names` FAILS — `axis_platform_cloud` and `axis_product_sense` are still present.

- [x] **Step 3: Create migration 003**

```sql
-- migrations/003_rename_axes.sql
-- Issue #13: align axis column names with docs/AXIS_MEASURE_SKILL.md
ALTER TABLE job_profiles RENAME COLUMN axis_platform_cloud TO axis_platform;
ALTER TABLE job_profiles RENAME COLUMN axis_product_sense  TO axis_product_ownership;
```

- [x] **Step 4: Update `JOB_PROFILE_COLUMNS` in `src/db.py`**

In `src/db.py`, replace the two lines:

```
    "axis_platform_cloud",
```
with
```
    "axis_platform",
```

and replace
```
    "axis_security_reliability",
    "axis_product_sense",
```
with
```
    "axis_security_reliability",
    "axis_product_ownership",
```

- [x] **Step 5: Update preset & return-dict keys in `src/profile_columns.py`**

In `default_axes_for_role_family`, every dict value uses keys `"backend"`, `"frontend"`, `"platform_cloud"`, `"ai_data"`, `"security_reliability"`, `"product_sense"`, `"fullstack_span"`. Rename the two affected keys: `"platform_cloud"` → `"platform"`, `"product_sense"` → `"product_ownership"`. (Find/replace across all 9 preset rows.)

In `build_profile_columns`'s returned dict, change:
- `"axis_platform_cloud": axes["platform_cloud"]` → `"axis_platform": axes["platform"]`
- `"axis_product_sense": axes["product_sense"]` → `"axis_product_ownership": axes["product_ownership"]`

(`axis_fullstack_span` and the others stay as-is for now.)

- [x] **Step 6: Run all tests to verify**

Run: `pytest tests/ -v`
Expected: all tests pass — migrations apply, columns rename, schema tests still green.

- [x] **Step 7: Commit**

```bash
git add migrations/003_rename_axes.sql src/db.py src/profile_columns.py tests/test_migrations.py
git commit -m "refactor: rename axis columns to match AXIS_MEASURE_SKILL.md (axis_platform, axis_product_ownership)"
```

---

### Task 5: `profile_columns.py` — switch axis source from presets to payload, add `fullstack_span`, drop fallbacks

This task is the heart of the refactor. After this step, `profile_columns.py` is a pure projection: every semantic field comes from the LLM payload; only `axis_fullstack_span` and `salary_tier` are computed in code.

**Files:**
- Modify: `src/profile_columns.py`
- Create: `tests/test_profile_columns.py`

- [x] **Step 1: Write the failing tests**

```python
# tests/test_profile_columns.py
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
```

- [x] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_profile_columns.py -v`
Expected: most fail — `fullstack_span` not exported, axes still come from presets, work_auth still goes through regex fallback when `explicit_constraints` mentions auth.

- [x] **Step 3: Rewrite `src/profile_columns.py`**

Replace the file contents with:

```python
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
```

- [x] **Step 4: Run all tests to verify**

Run: `pytest tests/ -v`
Expected: all tests pass — including the cross-check that `cols.keys() == JOB_PROFILE_COLUMNS - {"is_active"}` (db.py adds `is_active` itself in `save_extraction`).

- [x] **Step 5: Commit**

```bash
git add src/profile_columns.py tests/test_profile_columns.py
git commit -m "refactor: profile_columns reads axes from LLM payload; drop preset/regex fallbacks"
```

---

### Task 6: `extraction.txt` — bump to v2.0, embed axis rubric and Ford anchor

No automated test. The prompt loads at module import in Task 9; smoke test in Task 11 confirms the wired-up pipeline emits valid axes.

**Files:**
- Modify: `src/prompts/extraction.txt` (full rewrite)
- Reads from: `docs/AXIS_MEASURE_SKILL.md`, `docs/references/calibration_anchors.md`

- [x] **Step 1: Compose the prompt by running this Python one-shot**

This script reads the canonical sources, splices them into a fixed template, and writes `src/prompts/extraction.txt`. It is deterministic — re-running produces identical output (modulo source-file edits).

```bash
cd /home/ibrahim/Documents/job-match-agent
python <<'PY'
import re
from pathlib import Path

ROOT = Path(".")
skill = (ROOT / "docs" / "AXIS_MEASURE_SKILL.md").read_text()
anchors = (ROOT / "docs" / "references" / "calibration_anchors.md").read_text()

# Skill: strip YAML frontmatter (between first two '---' lines) and the H1
# title line, keep the body starting at "## What this skill does".
parts = skill.split("---\n", 2)
skill_body = parts[2] if len(parts) >= 3 else skill
start = skill_body.index("## What this skill does")
skill_body = skill_body[start:].rstrip()

# Ford anchor: section "## 2. Ford ..." up to (but not including) the next
# "## " section heading.
ford_match = re.search(
    r"^## 2\. Ford .*?(?=^## \d+\. |^---\s*$|\Z)",
    anchors,
    re.DOTALL | re.MULTILINE,
)
assert ford_match, "Ford anchor not found in calibration_anchors.md"
ford_section = ford_match.group(0).strip()

HEADER = """# prompt_version: 2.0
You extract structured software job profile data from job descriptions.

Return a complete structured object that matches the extraction schema provided by the caller.

Rules:
- Use only evidence from the provided job text.
- Do not invent company details, requirements, compensation, location, or technologies.
- If a nullable field is unknown, return null.
- If a list field has no strong evidence, return an empty list.
- Use enum values exactly as defined in the schema.
- Use "unknown" enum values only when the signal is genuinely ambiguous.
- `must_have_requirements` should include explicit requirements; uncertain requirements go to `preferred_requirements`.
- `evidence_snippets` should contain short verbatim quotes supporting key inferences.
- `extraction_confidence` must be a float in [0.0, 1.0].

Quality bar:
- Keep `summary` concise and factual.
- Classify skills into the correct category buckets.
- Ensure consistency between `seniority`, `responsibilities`, and `experience_requirements`.

Salary and compensation:
- Extract `salary_min`/`salary_max` only from explicit numeric figures. Do not estimate.
- `salary_currency`: derive from context ($ -> USD, C$ -> CAD, GBP, etc.) or null.
- `salary_period`: choose from "annual", "hourly", "monthly", "project". Default to "annual" for salaried roles when the period is implicit. Null only if truly ambiguous.

Work eligibility:
- `work_auth_required`: true only when the posting uses language like "must be authorized", "legally permitted to work". Null if not stated.
- `sponsorship_available`: false when posting says "no sponsorship", "cannot sponsor". True when sponsorship is explicitly offered. Null when not mentioned.
- `eligible_countries`: ISO alpha-2 codes only. Populate only when the posting explicitly restricts geography.
- `eligible_regions`: states or provinces, only when explicitly stated.

Education:
- `degree_required`: 0 when "degree not required", 1 if a Bachelor's is explicitly required, 2 for Master's, 3 for PhD. Null when not addressed.

Experience:
- `years_min` captures any floor mentioned (soft or hard).
- `years_min_hard`: use only when posting uses mandatory language ("must have X years", "X years required").

================================================================================
## Axis scoring rubric
================================================================================

"""

MIDDLE = """

Note: emit only the 6 primary axes (axis_backend, axis_frontend, axis_platform, axis_ai_data, axis_security_reliability, axis_product_ownership). axis_fullstack_span is computed downstream -- do NOT emit it.

================================================================================
## Few-shot anchor
================================================================================

"""

FOOTER = """

Expected axes block for the Ford anchor:
{
  "axes": {
    "axis_backend": 0.95,
    "axis_frontend": 0.05,
    "axis_platform": 0.75,
    "axis_ai_data": 0.25,
    "axis_security_reliability": 0.70,
    "axis_product_ownership": 0.35
  }
}
"""

out = HEADER + skill_body + MIDDLE + ford_section + FOOTER
Path("src/prompts/extraction.txt").write_text(out)
print(f"wrote src/prompts/extraction.txt ({len(out)} chars)")
PY
```

Expected output: `wrote src/prompts/extraction.txt (NNNN chars)` where NNNN is roughly 7000-9000.

- [x] **Step 2: Verify prompt parses**

Run:
```bash
cd /home/ibrahim/Documents/job-match-agent && python -c "
import sys
sys.path.insert(0, 'src')
from pipeline.extract import _read_prompt_and_version
import os
text, version = _read_prompt_and_version(os.path.join('src', 'prompts', 'extraction.txt'))
print(f'version={version!r} chars={len(text)}')
assert version == '2.0', f'expected 2.0, got {version!r}'
assert len(text) > 3000, f'expected >3000 chars, got {len(text)}'
print('OK')
"
```
Expected: `version='2.0' chars=...` then `OK`.

- [x] **Step 3: Commit**

```bash
git add src/prompts/extraction.txt
git commit -m "refactor: rewrite extraction prompt to v2.0 with embedded axis rubric and Ford anchor"
```

---

### Task 7: `AXIS_MEASURE_SKILL.md` — sync note

The rubric is duplicated into the prompt for caching. Mark the source-of-truth status explicitly.

**Files:**
- Modify: `docs/AXIS_MEASURE_SKILL.md` (top of file)

- [ ] **Step 1: Add a sync note**

Open `docs/AXIS_MEASURE_SKILL.md`. After the YAML frontmatter (the closing `---` on line 4) and before the `# JD Competency Scorer` H1, insert:

```markdown
> **⚠ Sync note:** This document is the source of truth for axis names,
> definitions, scoring philosophy, and calibration. Its body is embedded
> verbatim into `src/prompts/extraction.txt`. **When you edit this file,
> update `extraction.txt` and bump its `# prompt_version:` line.**
```

- [ ] **Step 2: Commit**

```bash
git add docs/AXIS_MEASURE_SKILL.md
git commit -m "docs: mark AXIS_MEASURE_SKILL.md as source of truth; flag prompt sync requirement"
```

---

### Task 8: `openai_client.extract_job_profile` — input array + `prompt_cache_key` + return usage + typed error

No automated test (would require mocking the OpenAI SDK; deferred per spec). Smoke test in Task 11 verifies wiring.

A typed exception (`MalformedOutputError`) is added so the caller in Task 10 can classify failures into the spec's two buckets: `malformed_output:` vs `api_error:`. API errors are no longer wrapped — they propagate naturally from the OpenAI SDK.

**Files:**
- Modify: `src/integrations/openai_client.py`
- Modify: `src/integrations/__init__.py`

- [ ] **Step 1: Replace `extract_job_profile` and add `MalformedOutputError`**

In `src/integrations/openai_client.py`, add the exception class near the top (after the imports, before `get_openai_client`):

```python
class MalformedOutputError(RuntimeError):
    """Raised when the LLM's response cannot be parsed into ExtractionResult.

    Distinguishes 'the model returned bad output' from 'the API call failed'
    so the extraction loop can apply the right error label.
    """
    pass
```

Then replace the existing `extract_job_profile` function (lines 34-53) with:

```python
def extract_job_profile(
    system_prompt: str,
    job_text: str,
    *,
    model: str,
    prompt_cache_key: str,
):
    """
    Extract structured job data via OpenAI Responses Structured Outputs.

    Returns a tuple of (parsed: ExtractionResult, usage: ResponseUsage). The usage
    object is required by the caller to track cached_tokens / input_tokens for
    observability — this is how we verify the >=30% cache target from issue #13.

    Uses an explicit input array (role: "system" + role: "user") so the system
    prompt is part of the cacheable prefix. `prompt_cache_key` ensures consistent
    cache routing across calls within a run.

    Errors:
    - Network / rate-limit / 5xx: propagate the SDK exception unchanged.
    - LLM returned no parseable structured output: raise MalformedOutputError.
    """
    client = get_openai_client()
    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"<job_description>\n{job_text}\n</job_description>",
                    }
                ],
            },
        ],
        text_format=ExtractionResult,
        prompt_cache_key=prompt_cache_key,
    )

    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise MalformedOutputError("Model returned no parsed structured output")
    return parsed, response.usage
```

- [ ] **Step 2: Export `MalformedOutputError` from the integrations package**

Replace the contents of `src/integrations/__init__.py` with:

```python
from .openai_client import (
    MalformedOutputError,
    call_llm,
    extract_job_profile,
    get_openai_client,
)

__all__ = [
    "MalformedOutputError",
    "call_llm",
    "extract_job_profile",
    "get_openai_client",
]
```

- [ ] **Step 3: Verify the module still imports cleanly**

Run:
```bash
cd /home/ibrahim/Documents/job-match-agent && python -c "
import sys
sys.path.insert(0, 'src'); sys.path.insert(0, '.')
from integrations import extract_job_profile, MalformedOutputError
import inspect
sig = inspect.signature(extract_job_profile)
assert 'prompt_cache_key' in sig.parameters
assert sig.parameters['prompt_cache_key'].kind.name == 'KEYWORD_ONLY'
assert issubclass(MalformedOutputError, RuntimeError)
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add src/integrations/openai_client.py src/integrations/__init__.py
git commit -m "refactor: openai extract_job_profile uses input array + prompt_cache_key; adds MalformedOutputError"
```

---

### Task 9: `extract.py` — module-level prompt load, `SCHEMA_VERSION = "2.0"`, `prompt_cache_key`

No automated test. The smoke test in Task 11 verifies wiring; module-level prompt load is verified by importing.

**Files:**
- Modify: `src/pipeline/extract.py`

- [ ] **Step 1: Replace constants and the loop signature**

Replace the contents of `src/pipeline/extract.py` with:

```python
import os
import sys
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from pydantic import ValidationError

from config.job_profile import JobProfile, ProfileMeta
from integrations import extract_job_profile, MalformedOutputError
from db import get_pending_extraction, save_extraction, fail_extraction
from utils import log_info


DEFAULT_MODEL = "gpt-4.1-nano"
SCHEMA_VERSION = "2.0"
_MAX_INPUT_CHARS = 60_000  # ~15k tokens; well under nano's window


def _read_prompt_and_version(prompt_path: str) -> tuple[str, str]:
    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    first_line = content.splitlines()[0].strip() if content else ""
    if first_line.startswith("# prompt_version:"):
        return content, first_line.split(":", 1)[1].strip()
    return content, "unknown"


_PROMPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'extraction.txt')
_SYSTEM_PROMPT, _PROMPT_VERSION = _read_prompt_and_version(_PROMPT_PATH)
_PROMPT_CACHE_KEY = f"extract:{SCHEMA_VERSION}:{_PROMPT_VERSION}:{DEFAULT_MODEL}"


def _attempt_extraction(job_text: str):
    """One call to the LLM. Returns (parsed, usage) or raises."""
    return extract_job_profile(
        system_prompt=_SYSTEM_PROMPT,
        job_text=job_text,
        model=DEFAULT_MODEL,
        prompt_cache_key=_PROMPT_CACHE_KEY,
    )


def extract_job_data():
    pending = get_pending_extraction(
        schema_version=SCHEMA_VERSION,
        prompt_version=_PROMPT_VERSION,
        model_version=DEFAULT_MODEL,
    )

    for job in pending:
        _process_one(job)


def _process_one(job: dict) -> None:
    db_job_id = job['job_posting_id']
    source_id = job['source_id']
    raw_text = job.get('raw_text')

    if not raw_text or not raw_text.strip():
        fail_extraction(db_job_id, "missing_description")
        log_info(f"Extraction skipped for job_id {db_job_id}: missing_description")
        return

    job_text = raw_text
    if len(job_text) > _MAX_INPUT_CHARS:
        log_info(
            f"Extraction truncating job_id {db_job_id}: "
            f"{len(job_text)} chars -> {_MAX_INPUT_CHARS}"
        )
        job_text = job_text[:_MAX_INPUT_CHARS]

    print(f"Processing job_id {db_job_id} with source_id {source_id}")

    extraction_result = None
    last_err: Exception | None = None
    last_kind: str | None = None
    for attempt in (1, 2):
        try:
            extraction_result, _usage = _attempt_extraction(job_text)
            break
        except (MalformedOutputError, ValidationError) as e:
            last_err = e
            last_kind = "malformed_output"
            log_info(
                f"Extraction attempt {attempt} ({last_kind}) for job_id {db_job_id}: {e}"
            )
        except Exception as e:
            last_err = e
            last_kind = "api_error"
            log_info(
                f"Extraction attempt {attempt} ({last_kind}) for job_id {db_job_id}: {e}"
            )

    if extraction_result is None:
        err_msg = f"{last_kind}: {last_err}"
        fail_extraction(db_job_id, err_msg)
        log_info(f"Extraction failed for job_id {db_job_id} after retry: {err_msg}")
        return

    profile_meta = ProfileMeta(
        schema_version=SCHEMA_VERSION,
        prompt_version=_PROMPT_VERSION,
        model=DEFAULT_MODEL,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    profile = JobProfile(
        job_id=source_id,
        profile_meta=profile_meta,
        **extraction_result.model_dump(),
    )
    save_extraction(db_job_id, profile)
    log_info(
        f"Extracted data for job_id {db_job_id}: "
        f"{profile.role_family} / {profile.seniority}"
    )
```

- [ ] **Step 2: Verify module imports cleanly**

Run:
```bash
cd /home/ibrahim/Documents/job-match-agent && python -c "
import sys
sys.path.insert(0, 'src'); sys.path.insert(0, '.')
from pipeline.extract import _SYSTEM_PROMPT, _PROMPT_VERSION, _PROMPT_CACHE_KEY, SCHEMA_VERSION
assert SCHEMA_VERSION == '2.0', SCHEMA_VERSION
assert _PROMPT_VERSION == '2.0', _PROMPT_VERSION
assert _PROMPT_CACHE_KEY == 'extract:2.0:2.0:gpt-4.1-nano', _PROMPT_CACHE_KEY
assert len(_SYSTEM_PROMPT) > 3000
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 3: Run unit tests to ensure nothing regressed**

Run: `pytest tests/ -v`
Expected: all tests pass (no extract.py-touching tests, but the import chain must stay healthy).

- [ ] **Step 4: Commit**

```bash
git add src/pipeline/extract.py
git commit -m "refactor: extract.py module-loads prompt, bumps SCHEMA_VERSION to 2.0, adds retry-once and truncation"
```

---

### Task 10: `extract.py` — usage accumulation + run-summary log

Adds the cached-token accounting required by the issue's ≥30% acceptance criterion.

**Files:**
- Modify: `src/pipeline/extract.py`

- [ ] **Step 1: Add accumulator state and update `_process_one`**

Edit `src/pipeline/extract.py` to make `_process_one` accept a stats dict and update it. Replace `extract_job_data` and `_process_one` with:

```python
def extract_job_data():
    pending = get_pending_extraction(
        schema_version=SCHEMA_VERSION,
        prompt_version=_PROMPT_VERSION,
        model_version=DEFAULT_MODEL,
    )

    stats = {
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "input_tokens": 0,
        "cached_tokens": 0,
    }

    for job in pending:
        stats["processed"] += 1
        _process_one(job, stats)

    if stats["processed"] == 0:
        log_info("extract: no pending jobs")
        return

    pct = (
        100.0 * stats["cached_tokens"] / stats["input_tokens"]
        if stats["input_tokens"] > 0
        else 0.0
    )
    log_info(
        f"extract: processed={stats['processed']} "
        f"succeeded={stats['succeeded']} failed={stats['failed']} "
        f"input_tokens={stats['input_tokens']} "
        f"cached_tokens={stats['cached_tokens']} ({pct:.1f}%)"
    )
    print(
        f"Extraction summary: {stats['succeeded']}/{stats['processed']} "
        f"jobs, cached {stats['cached_tokens']}/{stats['input_tokens']} "
        f"tokens ({pct:.1f}%)"
    )


def _process_one(job: dict, stats: dict) -> None:
    db_job_id = job['job_posting_id']
    source_id = job['source_id']
    raw_text = job.get('raw_text')

    if not raw_text or not raw_text.strip():
        fail_extraction(db_job_id, "missing_description")
        log_info(f"Extraction skipped for job_id {db_job_id}: missing_description")
        stats["failed"] += 1
        return

    job_text = raw_text
    if len(job_text) > _MAX_INPUT_CHARS:
        log_info(
            f"Extraction truncating job_id {db_job_id}: "
            f"{len(job_text)} chars -> {_MAX_INPUT_CHARS}"
        )
        job_text = job_text[:_MAX_INPUT_CHARS]

    print(f"Processing job_id {db_job_id} with source_id {source_id}")

    extraction_result = None
    usage = None
    last_err: Exception | None = None
    last_kind: str | None = None
    for attempt in (1, 2):
        try:
            extraction_result, usage = _attempt_extraction(job_text)
            break
        except (MalformedOutputError, ValidationError) as e:
            last_err = e
            last_kind = "malformed_output"
            log_info(
                f"Extraction attempt {attempt} ({last_kind}) for job_id {db_job_id}: {e}"
            )
        except Exception as e:
            last_err = e
            last_kind = "api_error"
            log_info(
                f"Extraction attempt {attempt} ({last_kind}) for job_id {db_job_id}: {e}"
            )

    if extraction_result is None:
        err_msg = f"{last_kind}: {last_err}"
        fail_extraction(db_job_id, err_msg)
        log_info(f"Extraction failed for job_id {db_job_id} after retry: {err_msg}")
        stats["failed"] += 1
        return

    if usage is not None:
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        details = getattr(usage, "input_tokens_details", None)
        cached = getattr(details, "cached_tokens", 0) if details is not None else 0
        cached = cached or 0
        stats["input_tokens"] += input_tokens
        stats["cached_tokens"] += cached
        pct = 100.0 * cached / input_tokens if input_tokens > 0 else 0.0
        log_info(
            f"extract: posting_id={db_job_id} model={DEFAULT_MODEL} "
            f"input={input_tokens} cached={cached} ({pct:.1f}%)"
        )

    profile_meta = ProfileMeta(
        schema_version=SCHEMA_VERSION,
        prompt_version=_PROMPT_VERSION,
        model=DEFAULT_MODEL,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    profile = JobProfile(
        job_id=source_id,
        profile_meta=profile_meta,
        **extraction_result.model_dump(),
    )
    save_extraction(db_job_id, profile)
    stats["succeeded"] += 1
    log_info(
        f"Extracted data for job_id {db_job_id}: "
        f"{profile.role_family} / {profile.seniority}"
    )
```

- [ ] **Step 2: Verify module imports cleanly and `_process_one` signature is correct**

Run:
```bash
cd /home/ibrahim/Documents/job-match-agent && python -c "
import sys
sys.path.insert(0, 'src'); sys.path.insert(0, '.')
import inspect
from pipeline.extract import _process_one, extract_job_data
sig = inspect.signature(_process_one)
assert list(sig.parameters) == ['job', 'stats'], list(sig.parameters)
print('OK')
"
```
Expected: `OK`.

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add src/pipeline/extract.py
git commit -m "feat: extract.py logs cached/input token ratio per job and per run"
```

---

### Task 11: End-to-end smoke test (manual)

Verifies the full pipeline against the real OpenAI API on a small sample. This is **manual** because it costs money and requires a real API key.

**Files:** none (run-only)

- [ ] **Step 1: Make a working copy of the DB**

```bash
cd /home/ibrahim/Documents/job-match-agent
cp data/job_matcher.db data/job_matcher.db.before-issue13
```

- [ ] **Step 2: Apply migrations to the live DB**

```bash
cd /home/ibrahim/Documents/job-match-agent
python -c "
import sys
sys.path.insert(0, 'src'); sys.path.insert(0, '.')
import db
db.init_db()
print('migrations applied')
"
```
Expected: `migrations applied`. If migration 003 fails because the previous DB run had partially renamed columns, restore from `.before-issue13` and investigate.

- [ ] **Step 3: Verify the renamed columns**

```bash
sqlite3 data/job_matcher.db "PRAGMA table_info(job_profiles);" | grep axis_
```
Expected output includes `axis_platform`, `axis_product_ownership`, `axis_fullstack_span`. Should NOT include `axis_platform_cloud` or `axis_product_sense`.

- [ ] **Step 4: Run the pipeline on a small sample**

The cleanest way to limit blast radius is to run extraction on a few jobs. The whole pipeline:

```bash
cd /home/ibrahim/Documents/job-match-agent && source venv/bin/activate && python src/main.py
```

If you want to limit to a few jobs first, manually update a handful of postings to `profile_status='current'` so they're skipped, then run.

Expected:
- Pipeline runs without exceptions.
- Per-job log lines like `extract: posting_id=42 ... input=1923 cached=1612 (84%) ...` appear in `logs/job_matcher.log`.
- Final summary line: `extract: processed=N succeeded=M failed=K input_tokens=... cached_tokens=... (X%)`.
- On a fresh-after-version-bump run, the **first** call's `cached` will be ~0; **subsequent** calls in the same run should report cached% ≥ 30. The run summary will reflect the average.

- [ ] **Step 5: Spot-check the resulting data**

```bash
sqlite3 data/job_matcher.db "
SELECT job_posting_id, role_family, seniority,
       round(axis_backend, 2), round(axis_frontend, 2),
       round(axis_platform, 2), round(axis_ai_data, 2),
       round(axis_security_reliability, 2), round(axis_product_ownership, 2),
       round(axis_fullstack_span, 2)
FROM job_profiles
WHERE is_active = 1
ORDER BY job_posting_id DESC
LIMIT 10;
"
```

Expected:
- Axis values **vary** across jobs (a backend posting has high `axis_backend` and low `axis_frontend`; a fullstack posting is more balanced).
- `axis_fullstack_span` for a backend-heavy row equals `2 * frontend` rounded; for a balanced row equals `1.0`.
- No row is the canned preset 0.45/0.10/0.45/0.30/0.45/0.20 — that confirms the LLM is scoring, not the dropped fallback.

- [ ] **Step 6: Verify the cache acceptance criterion**

```bash
tail -20 logs/job_matcher.log | grep "extract: processed="
```
Expected: a single summary line whose `(X%)` is ≥ 30.0% on a run with multiple jobs.

If the cache % is below 30% on a multi-job run, root-cause possibilities:
1. The `prompts/extraction.txt` was edited mid-run (every byte change invalidates the prefix).
2. Job descriptions are very long, dwarfing the cached prefix. Compare `input_tokens` to ~2k (the prefix size) — if every JD is 10k+ tokens, even 100% prefix cache caps the ratio at ~20%.
3. The `prompt_cache_key` is changing per call (it's a constant, but worth verifying with `python -c "from pipeline.extract import _PROMPT_CACHE_KEY; print(_PROMPT_CACHE_KEY)"`).

- [ ] **Step 7: Restore safety**

If anything looks wrong, restore the original DB:

```bash
cp data/job_matcher.db.before-issue13 data/job_matcher.db
```

Otherwise, leave the backup in place until the change is confirmed in another run, then delete:

```bash
rm data/job_matcher.db.before-issue13
```

---

## Acceptance check

After all tasks above, the issue's acceptance criteria are satisfied:

- [x] **All unprocessed jobs processed without errors** — Tasks 9–10 wire up retry-once and explicit failure handling.
- [x] **Every posting has a `job_profiles` row with LLM-populated axes** — Task 5 reads axes from `payload["axes"]`; Task 11 confirms via `SELECT axis_*`.
- [x] **Cached tokens / prompt tokens ≥ 30%** — Tasks 6, 8, 9, 10 produce a stable cacheable prefix and `prompt_cache_key`; Task 11 step 6 verifies.
- [x] **No hardcoded axis values remain** — Task 5 deletes `default_axes_for_role_family`.
- [x] **Schemas fully aligned** — Task 2 (`Axes`), Task 3 (`axes` field), Task 4 (column renames) close all three sides.
- [x] **`prompt_cache_key` set on every call** — Task 8 makes it a required keyword-only parameter on `extract_job_profile`.
