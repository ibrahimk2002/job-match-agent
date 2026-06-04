# PR 1 — Schema Cleanup: Drop Overengineered Fields

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `eligible_countries`, `eligible_regions`, and `explicit_constraints` from the job profile schema — they cost tokens and storage but are never used in matching or display.

**Architecture:** Drop three fields from Pydantic models, remove their DB column projections from `profile_columns.py` and `JOB_PROFILE_COLUMNS`, delete the corresponding prompt instructions, and update test fixtures. The SQLite table columns (`eligible_countries_json`, `eligible_regions_json`) are left as dead weight — PR 2 (Postgres migration) replaces the entire schema with a fresh baseline. No behavior change to extraction or matching.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, SQLite (temporary — PR 2 migrates to Postgres)

---

## File Map

| Action | File | What changes |
|---|---|---|
| Modify | `src/models/job_profile.py` | Remove `eligible_countries`, `eligible_regions` from `WorkEligibility`; remove `explicit_constraints` from `JobProfile` and `ExtractionResult` |
| Modify | `src/profile_columns.py` | Remove extraction + output of `eligible_countries_json` / `eligible_regions_json` |
| Modify | `src/db.py` | Remove `eligible_countries_json` and `eligible_regions_json` from `JOB_PROFILE_COLUMNS` |
| Modify | `src/prompts/extraction.txt` | Remove `eligible_countries` and `eligible_regions` instructions |
| Modify | `tests/test_job_profile_schema.py` | Add absence tests; remove dropped fields from `_valid_extraction_payload()` |
| Modify | `tests/test_profile_columns.py` | Remove dropped fields from `_payload_with_axes()` and from `test_build_columns_passes_through_work_eligibility_directly` |

---

## Task 1: Write failing tests asserting field absence

**Files:**
- Modify: `tests/test_job_profile_schema.py`

- [ ] **Step 1: Add absence tests at the bottom of `tests/test_job_profile_schema.py`**

  Open the file and append:

  ```python
  def test_work_eligibility_does_not_have_geographic_restriction_fields():
      from models.job_profile import WorkEligibility
      assert "eligible_countries" not in WorkEligibility.model_fields
      assert "eligible_regions" not in WorkEligibility.model_fields


  def test_job_profile_does_not_have_explicit_constraints():
      assert "explicit_constraints" not in JobProfile.model_fields
      assert "explicit_constraints" not in ExtractionResult.model_fields
  ```

- [ ] **Step 2: Run the new tests — they must FAIL**

  ```
  pytest tests/test_job_profile_schema.py::test_work_eligibility_does_not_have_geographic_restriction_fields tests/test_job_profile_schema.py::test_job_profile_does_not_have_explicit_constraints -v
  ```

  Expected: both tests FAIL with `AssertionError` (the fields still exist).

---

## Task 2: Remove fields from Pydantic models

**Files:**
- Modify: `src/models/job_profile.py`

- [ ] **Step 1: Remove `eligible_countries` and `eligible_regions` from `WorkEligibility`**

  In `src/models/job_profile.py`, the `WorkEligibility` class currently looks like:

  ```python
  class WorkEligibility(BaseModel):
      work_auth_required: bool | None = Field(...)
      sponsorship_available: bool | None = Field(...)
      eligible_countries: list[str] | None = Field(
          None,
          description=(
              "ISO 3166-1 alpha-2 country codes where the role is eligible (e.g. ['US', 'CA']). "
              "Null if not restricted or not stated."
          ),
      )
      eligible_regions: list[str] | None = Field(
          None,
          description="Sub-national regions or states explicitly stated (e.g. ['California', 'Ontario']). Null if not stated.",
      )
  ```

  Remove the `eligible_countries` and `eligible_regions` fields so it becomes:

  ```python
  class WorkEligibility(BaseModel):
      work_auth_required: bool | None = Field(
          None,
          description=(
              "True if the posting requires candidates to already be authorized to work "
              "(e.g. 'must be authorized to work in the US'). Null if not stated."
          ),
      )
      sponsorship_available: bool | None = Field(
          None,
          description=(
              "True if employer will sponsor visas. False if they explicitly state no sponsorship "
              "('we do not sponsor'). Null if not mentioned."
          ),
      )
  ```

- [ ] **Step 2: Remove `explicit_constraints` from `JobProfile`**

  In `src/models/job_profile.py`, find `JobProfile` and remove the line:

  ```python
  explicit_constraints: list[str]
  ```

- [ ] **Step 3: Remove `explicit_constraints` from `ExtractionResult`**

  In the same file, find `ExtractionResult` and remove the line:

  ```python
  explicit_constraints: list[str]
  ```

- [ ] **Step 4: Run the absence tests — they must now PASS**

  ```
  pytest tests/test_job_profile_schema.py::test_work_eligibility_does_not_have_geographic_restriction_fields tests/test_job_profile_schema.py::test_job_profile_does_not_have_explicit_constraints -v
  ```

  Expected: both PASS.

---

## Task 3: Remove column projections from `profile_columns.py` and `db.py`

**Files:**
- Modify: `src/profile_columns.py`
- Modify: `src/db.py`

These two files must change together — `test_build_columns_keys_match_db_constants` asserts that the keys returned by `build_profile_columns` exactly equal `JOB_PROFILE_COLUMNS - {"is_active"}`. Both must shrink by the same two columns.

- [ ] **Step 1: Remove `eligible_countries` / `eligible_regions` extraction and output from `src/profile_columns.py`**

  Remove these two lines near the top of `build_profile_columns`:

  ```python
  eligible_countries = work_eligibility.get("eligible_countries")
  eligible_regions = work_eligibility.get("eligible_regions")
  ```

  And remove these two lines from the returned dict:

  ```python
  "eligible_countries_json": json.dumps(eligible_countries) if eligible_countries else None,
  "eligible_regions_json": json.dumps(eligible_regions) if eligible_regions else None,
  ```

- [ ] **Step 2: Remove the two column names from `JOB_PROFILE_COLUMNS` in `src/db.py`**

  Find `JOB_PROFILE_COLUMNS` (a list starting at line ~25) and remove these two entries:

  ```python
  "eligible_countries_json",
  "eligible_regions_json",
  ```

- [ ] **Step 3: Run the profile columns tests**

  ```
  pytest tests/test_profile_columns.py -v
  ```

  Expected: `test_build_columns_keys_match_db_constants` and the other profile column tests PASS. (The fixture still has `"eligible_countries"` in the payload dict — that's fine, `build_profile_columns` just won't read it. We'll clean it up in Task 5.)

---

## Task 4: Remove instructions from extraction prompt

**Files:**
- Modify: `src/prompts/extraction.txt`

- [ ] **Step 1: Remove the `eligible_countries` and `eligible_regions` instructions**

  In `src/prompts/extraction.txt`, under the "Work eligibility:" section (around lines 28–32), the current content is:

  ```
  Work eligibility:
  - `work_auth_required`: true only when the posting uses language like "must be authorized", "legally permitted to work". Null if not stated.
  - `sponsorship_available`: false when posting says "no sponsorship", "cannot sponsor". True when sponsorship is explicitly offered. Null when not mentioned.
  - `eligible_countries`: ISO alpha-2 codes only. Populate only when the posting explicitly restricts geography.
  - `eligible_regions`: states or provinces, only when explicitly stated.
  ```

  Remove the last two bullet points so the section becomes:

  ```
  Work eligibility:
  - `work_auth_required`: true only when the posting uses language like "must be authorized", "legally permitted to work". Null if not stated.
  - `sponsorship_available`: false when posting says "no sponsorship", "cannot sponsor". True when sponsorship is explicitly offered. Null when not mentioned.
  ```

---

## Task 5: Update test fixtures

Remove the now-dropped fields from test helper payloads so fixtures reflect the current schema.

**Files:**
- Modify: `tests/test_job_profile_schema.py`
- Modify: `tests/test_profile_columns.py`

- [ ] **Step 1: Update `_valid_extraction_payload()` in `tests/test_job_profile_schema.py`**

  Remove `"explicit_constraints": [],` from the dict returned by `_valid_extraction_payload()`.

  Before (lines 62–66):
  ```python
  "education_requirements": [],
  "domain_signals": [],
  "explicit_constraints": [],
  "extraction_confidence": 0.85,
  "evidence_snippets": [],
  ```

  After:
  ```python
  "education_requirements": [],
  "domain_signals": [],
  "extraction_confidence": 0.85,
  "evidence_snippets": [],
  ```

- [ ] **Step 2: Update `_payload_with_axes()` in `tests/test_profile_columns.py`**

  Remove `"eligible_countries": ["US"]` and `"eligible_regions": None` from the `work_eligibility` dict, and remove `"explicit_constraints": []` from the top-level dict.

  Before:
  ```python
  "work_eligibility": {
      "work_auth_required": True,
      "sponsorship_available": False,
      "eligible_countries": ["US"],
      "eligible_regions": None,
  },
  ...
  "explicit_constraints": [],
  ```

  After:
  ```python
  "work_eligibility": {
      "work_auth_required": True,
      "sponsorship_available": False,
  },
  ...
  ```
  (Remove the `"explicit_constraints": []` line entirely.)

- [ ] **Step 3: Update `test_build_columns_passes_through_work_eligibility_directly` in `tests/test_profile_columns.py`**

  Remove the `explicit_constraints` assignment and its comment:

  Before:
  ```python
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
  ```

  After:
  ```python
  def test_build_columns_passes_through_work_eligibility_directly():
      payload = _payload_with_axes()
      payload["work_eligibility"]["work_auth_required"] = True
      payload["work_eligibility"]["sponsorship_available"] = False
      cols = build_profile_columns(
          payload, job_posting_id=1, content_hash="abc",
      )
      assert cols["work_auth_required"] == 1
      assert cols["sponsorship_available"] == 0
  ```

---

## Task 6: Full test suite verification

- [ ] **Step 1: Run the full test suite**

  ```
  pytest tests/ -v
  ```

  Expected: all tests PASS. No references to `eligible_countries`, `eligible_regions`, or `explicit_constraints` should remain in any test assertion.

- [ ] **Step 2: Verify `profile_json` no longer contains dropped fields**

  Run a quick smoke check in a Python REPL (or add a temporary `print` in a test) to confirm:

  ```python
  import json
  from models.job_profile import ExtractionResult

  result = ExtractionResult.model_validate({
      "normalized_title": "Backend Engineer",
      "role_family": "backend",
      "seniority": "mid",
      "employment_type": "full_time",
      "work_mode": "remote",
      "location_scope": "US",
      "salary": {},
      "work_eligibility": {},
      "degree_required": 1,
      "summary": "Build APIs.",
      "must_have_requirements": ["Python"],
      "preferred_requirements": [],
      "responsibilities": ["Ship code"],
      "skills": {"languages": ["Python"], "frameworks": [], "cloud": [], "databases": [], "devops": [], "ai_ml": [], "other_tools": [], "concepts": []},
      "experience_requirements": {"years_min": 3, "years_max": None, "level_signal": "mid", "years_min_hard": None},
      "education_requirements": [],
      "domain_signals": [],
      "extraction_confidence": 0.9,
      "evidence_snippets": [],
      "axes": {"axis_backend": 0.7, "axis_frontend": 0.1, "axis_platform": 0.3, "axis_ai_data": 0.2, "axis_security_reliability": 0.4, "axis_product_ownership": 0.3},
  })
  dumped = result.model_dump()
  assert "explicit_constraints" not in dumped
  assert "eligible_countries" not in dumped.get("work_eligibility", {})
  assert "eligible_regions" not in dumped.get("work_eligibility", {})
  print("All assertions pass — dropped fields are gone from profile_json")
  ```

- [ ] **Step 3: Commit**

  ```bash
  git add src/models/job_profile.py src/profile_columns.py src/db.py src/prompts/extraction.txt tests/test_job_profile_schema.py tests/test_profile_columns.py
  git commit -m "refactor(schema): drop eligible_countries, eligible_regions, explicit_constraints

  Fields were never used in matching or display — pure token and storage cost.
  DB columns left as dead weight; PR 2 (Postgres migration) creates a fresh baseline schema."
  ```
