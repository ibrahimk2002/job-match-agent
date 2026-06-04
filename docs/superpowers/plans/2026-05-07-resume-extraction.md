# Resume Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resume extraction pipeline that mirrors the job-side flow — PDF in, `UserProfile` stored in `user_profiles` SQLite table with denormalized columns — enabling symmetric matching without per-job LLM calls.

**Architecture:** PDF text extracted via `pypdf`, sent to gpt-4.1-nano via Responses API with structured output, result stored in `user_profiles` with same versioning tuple `(content_hash, schema_version, prompt_version, model_version)` as `job_profiles`. Extract once, query denormalized columns many times.

**Tech Stack:** Python 3.11+, Pydantic v2, pypdf, OpenAI Responses API, SQLite, argparse, pytest

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Replace | `config/user_profile.py` | Full Pydantic schema: `ResumeAxes`, `ResumeSkills`, `WorkExperience`, `ResumeEducation`, `CareerPreferences`, `ResumeWorkAuth`, `ResumeExtractionResult`, `UserProfile` |
| Create | `migrations/004_add_user_profiles.sql` | `users` + `user_profiles` tables with versioning, unique-active index |
| Create | `src/user_profile_columns.py` | `build_profile_columns(profile) -> dict` + `USER_PROFILE_COLUMNS` constant |
| Modify | `src/db.py` | Add `get_or_create_user`, `get_active_user_profile`, `save_resume_extraction` |
| Modify | `requirements.txt` | Add `pypdf` |
| Create | `src/prompts/resume_extraction.txt` | System prompt with evidence-weighted axis rubric + calibration anchors |
| Modify | `src/integrations/openai_client.py` | Add `extract_resume_profile()` |
| Modify | `src/integrations/__init__.py` | Export `extract_resume_profile` |
| Create | `src/pipeline/extract_resume.py` | PDF extraction pipeline: hash → version check → LLM → save |
| Create | `src/cli.py` | `python -m src.cli ingest-resume <pdf_path> --email <email>` |
| Modify | `src/prompts/extraction.txt` | Add experience-depth + responsibility-framing signals, bump to v2.3 |
| Create | `tests/test_user_profile_columns.py` | Upsert invariant: keys match `USER_PROFILE_COLUMNS` |
| Create | `tests/test_db_user_profiles.py` | Migration, versioning, unique-index, `get_or_create_user` idempotency |
| Create | `tests/test_extract_resume.py` | Mock PDF + API; assert `UserProfile` saved with correct denormalized columns |

---

## Task 1: Replace `config/user_profile.py` with full Pydantic schema

**Files:**
- Modify: `config/user_profile.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_user_profile_schema.py  (add to existing file or create new)
# Run: pytest tests/test_user_profile_schema.py -v
# Expected: ImportError or AttributeError — classes don't exist yet

def test_user_profile_models_are_importable():
    from config.user_profile import (
        ResumeAxes, ResumeSkills, WorkExperience, ResumeEducation,
        CareerPreferences, ResumeWorkAuth, ResumeExtractionResult, UserProfile,
    )
    from config.job_profile import ProfileMeta

    axes = ResumeAxes(
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
        evidence_snippets=[{"field": "primary_role_family", "quote": "built REST APIs"}],
    )
    assert profile.full_name == "Jane Doe"
    assert profile.meta.schema_version == "1.0"
```

- [ ] **Step 2: Run the test to verify it fails**

```
pytest tests/test_user_profile_schema.py::test_user_profile_models_are_importable -v
```

Expected: `FAILED` with `ImportError` (old stub has wrong class names)

- [ ] **Step 3: Replace `config/user_profile.py`**

```python
# config/user_profile.py
from pydantic import BaseModel

from config.job_profile import ProfileMeta  # reused unchanged


class ResumeAxes(BaseModel):
    axis_backend: float
    axis_frontend: float
    axis_platform: float
    axis_ai_data: float
    axis_security_reliability: float
    axis_product_ownership: float


class ResumeSkills(BaseModel):
    languages: list[str]
    frameworks: list[str]
    cloud: list[str]
    databases: list[str]
    devops: list[str]
    ai_ml: list[str]
    other_tools: list[str]
    concepts: list[str]


class WorkExperience(BaseModel):
    title: str
    company: str
    years: float
    level_signal: str   # "intern"|"junior"|"mid"|"senior"|"staff"|"principal"
    key_contributions: list[str]


class ResumeEducation(BaseModel):
    degree_level: int   # 0=none/trade, 1=bachelor, 2=master, 3=phd
    fields: list[str]


class CareerPreferences(BaseModel):
    desired_roles: list[str]
    desired_role_families: list[str]
    desired_seniority: str              # "junior"|"mid"|"senior"|"staff"|"any"
    desired_work_modes: list[str]
    desired_locations: list[str]
    desired_salary_min: int | None
    desired_salary_max: int | None
    desired_salary_currency: str        # "CAD"|"USD"


class ResumeWorkAuth(BaseModel):
    canada: bool
    us: bool
    sponsorship_needed: bool | None     # null if not stated


class ResumeExtractionResult(BaseModel):
    full_name: str | None
    total_years_experience: float
    current_level: str              # "student"|"junior"|"mid"|"senior"|"staff"|"principal"
    primary_role_family: str        # "backend"|"frontend"|"fullstack"|"platform"|"ai_ml"|"security"|"product"
    axes: ResumeAxes
    skills: ResumeSkills
    work_experience: list[WorkExperience]
    education: ResumeEducation
    preferences: CareerPreferences
    work_auth: ResumeWorkAuth
    extraction_confidence: float
    evidence_snippets: list[dict]


class UserProfile(BaseModel):
    meta: ProfileMeta
    full_name: str | None
    total_years_experience: float
    current_level: str
    primary_role_family: str
    axes: ResumeAxes
    skills: ResumeSkills
    work_experience: list[WorkExperience]
    education: ResumeEducation
    preferences: CareerPreferences
    work_auth: ResumeWorkAuth
    extraction_confidence: float
    evidence_snippets: list[dict]
```

- [ ] **Step 4: Run the test to verify it passes**

```
pytest tests/test_user_profile_schema.py::test_user_profile_models_are_importable -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add config/user_profile.py tests/test_user_profile_schema.py
git commit -m "feat(schema): replace UserProfile stub with full resume extraction schema"
```

---

## Task 2: Create `migrations/004_add_user_profiles.sql`

**Files:**
- Create: `migrations/004_add_user_profiles.sql`
- Create: `tests/test_db_user_profiles.py` (initial table-existence tests)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_db_user_profiles.py

def _column_names(db_path, table):
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [r[1] for r in rows]
    finally:
        conn.close()


def test_users_table_exists(temp_db):
    cols = _column_names(temp_db, "users")
    assert "id" in cols
    assert "email" in cols
    assert "created_at" in cols


def test_user_profiles_table_exists(temp_db):
    cols = _column_names(temp_db, "user_profiles")
    expected = [
        "id", "user_id", "content_hash", "schema_version", "prompt_version",
        "model_version", "is_active", "invalidated_reason", "profile_json",
        "full_name", "total_years_experience", "current_level", "primary_role_family",
        "axis_backend", "axis_frontend", "axis_platform", "axis_ai_data",
        "axis_security_reliability", "axis_product_ownership", "axis_fullstack_span",
        "skills_languages", "skills_frameworks", "skills_cloud",
        "desired_role_families", "desired_seniority", "desired_work_modes",
        "desired_locations", "desired_salary_min", "desired_salary_max",
        "desired_salary_currency", "work_auth_canada", "work_auth_us",
        "sponsorship_needed", "degree_level", "created_at",
    ]
    for col in expected:
        assert col in cols, f"missing column: {col}"
```

- [ ] **Step 2: Run the test to verify it fails**

```
pytest tests/test_db_user_profiles.py::test_users_table_exists tests/test_db_user_profiles.py::test_user_profiles_table_exists -v
```

Expected: `FAILED` — tables don't exist yet

- [ ] **Step 3: Create the migration**

```sql
-- migrations/004_add_user_profiles.sql

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT NOT NULL UNIQUE,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                   INTEGER NOT NULL REFERENCES users(id),
    content_hash              TEXT NOT NULL,
    schema_version            TEXT NOT NULL,
    prompt_version            TEXT NOT NULL,
    model_version             TEXT NOT NULL,
    is_active                 INTEGER NOT NULL DEFAULT 1,
    invalidated_reason        TEXT,
    profile_json              TEXT NOT NULL,

    -- identity
    full_name                 TEXT,
    total_years_experience    REAL,
    current_level             TEXT,
    primary_role_family       TEXT,

    -- capability axes
    axis_backend              REAL,
    axis_frontend             REAL,
    axis_platform             REAL,
    axis_ai_data              REAL,
    axis_security_reliability REAL,
    axis_product_ownership    REAL,
    axis_fullstack_span       REAL,

    -- top skills (JSON arrays as TEXT)
    skills_languages          TEXT,
    skills_frameworks         TEXT,
    skills_cloud              TEXT,

    -- preferences
    desired_role_families     TEXT,
    desired_seniority         TEXT,
    desired_work_modes        TEXT,
    desired_locations         TEXT,
    desired_salary_min        INTEGER,
    desired_salary_max        INTEGER,
    desired_salary_currency   TEXT,

    -- work eligibility
    work_auth_canada          INTEGER,
    work_auth_us              INTEGER,
    sponsorship_needed        INTEGER,

    -- education
    degree_level              INTEGER,

    created_at                TEXT DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_user_profiles_active
    ON user_profiles(user_id) WHERE is_active = 1;
```

- [ ] **Step 4: Run the test to verify it passes**

```
pytest tests/test_db_user_profiles.py::test_users_table_exists tests/test_db_user_profiles.py::test_user_profiles_table_exists -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add migrations/004_add_user_profiles.sql tests/test_db_user_profiles.py
git commit -m "feat(db): add users and user_profiles tables via migration 004"
```

---

## Task 3: Create `src/user_profile_columns.py`

**Files:**
- Create: `src/user_profile_columns.py`
- Create: `tests/test_user_profile_columns.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_user_profile_columns.py
import pytest


def _make_profile():
    from config.user_profile import (
        UserProfile, ResumeAxes, ResumeSkills,
        WorkExperience, ResumeEducation, CareerPreferences, ResumeWorkAuth,
    )
    from config.job_profile import ProfileMeta
    return UserProfile(
        meta=ProfileMeta(
            schema_version="1.0", prompt_version="1.0",
            model="gpt-4.1-nano", generated_at="2026-05-07T00:00:00+00:00",
        ),
        full_name="Jane Doe",
        total_years_experience=3.0,
        current_level="junior",
        primary_role_family="backend",
        axes=ResumeAxes(
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
```

- [ ] **Step 2: Run the test to verify it fails**

```
pytest tests/test_user_profile_columns.py -v
```

Expected: `FAILED` with `ModuleNotFoundError: No module named 'user_profile_columns'`

- [ ] **Step 3: Create `src/user_profile_columns.py`**

```python
# src/user_profile_columns.py
import json

from config.user_profile import UserProfile


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
```

- [ ] **Step 4: Run the tests to verify they pass**

```
pytest tests/test_user_profile_columns.py -v
```

Expected: all 4 `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/user_profile_columns.py tests/test_user_profile_columns.py
git commit -m "feat(columns): add user_profile_columns.py projecting UserProfile to denormalized dict"
```

---

## Task 4: Add DB functions to `src/db.py`

**Files:**
- Modify: `src/db.py` (append 3 functions)
- Modify: `tests/test_db_user_profiles.py` (add CRUD tests)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_db_user_profiles.py`)

```python
# Append to tests/test_db_user_profiles.py


def _make_user_profile():
    """Reusable minimal UserProfile for DB tests."""
    from config.user_profile import (
        UserProfile, ResumeAxes, ResumeSkills,
        WorkExperience, ResumeEducation, CareerPreferences, ResumeWorkAuth,
    )
    from config.job_profile import ProfileMeta
    return UserProfile(
        meta=ProfileMeta(
            schema_version="1.0", prompt_version="1.0",
            model="gpt-4.1-nano", generated_at="2026-05-07T00:00:00+00:00",
        ),
        full_name="Test User",
        total_years_experience=2.0,
        current_level="junior",
        primary_role_family="backend",
        axes=ResumeAxes(
            axis_backend=0.5, axis_frontend=0.1, axis_platform=0.2,
            axis_ai_data=0.1, axis_security_reliability=0.2, axis_product_ownership=0.1,
        ),
        skills=ResumeSkills(
            languages=["Python"], frameworks=[], cloud=[], databases=[],
            devops=[], ai_ml=[], other_tools=[], concepts=[],
        ),
        work_experience=[],
        education=ResumeEducation(degree_level=1, fields=["CS"]),
        preferences=CareerPreferences(
            desired_roles=[], desired_role_families=["backend"],
            desired_seniority="mid", desired_work_modes=["remote"],
            desired_locations=[], desired_salary_min=None,
            desired_salary_max=None, desired_salary_currency="CAD",
        ),
        work_auth=ResumeWorkAuth(canada=True, us=False, sponsorship_needed=None),
        extraction_confidence=0.8,
        evidence_snippets=[],
    )


def test_get_or_create_user_idempotent(temp_db):
    import db
    user_id_1 = db.get_or_create_user("alice@example.com")
    user_id_2 = db.get_or_create_user("alice@example.com")
    assert isinstance(user_id_1, int)
    assert user_id_1 == user_id_2


def test_get_or_create_user_different_emails(temp_db):
    import db
    id_a = db.get_or_create_user("alice@example.com")
    id_b = db.get_or_create_user("bob@example.com")
    assert id_a != id_b


def test_get_active_user_profile_returns_none_when_empty(temp_db):
    import db
    user_id = db.get_or_create_user("alice@example.com")
    result = db.get_active_user_profile(user_id)
    assert result is None


def test_save_resume_extraction_stores_row(temp_db):
    import db
    import sqlite3
    from user_profile_columns import build_profile_columns

    user_id = db.get_or_create_user("alice@example.com")
    profile = _make_user_profile()
    db.save_resume_extraction(user_id, profile, build_profile_columns(profile), content_hash="abc123")

    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM user_profiles WHERE user_id = ? AND is_active = 1", (user_id,)
        ).fetchone()
        assert row is not None
        assert row["current_level"] == "junior"
        assert row["content_hash"] == "abc123"
        assert row["is_active"] == 1
    finally:
        conn.close()


def test_get_active_user_profile_returns_row_after_save(temp_db):
    import db
    from user_profile_columns import build_profile_columns

    user_id = db.get_or_create_user("alice@example.com")
    profile = _make_user_profile()
    db.save_resume_extraction(user_id, profile, build_profile_columns(profile), content_hash="abc123")

    result = db.get_active_user_profile(user_id)
    assert result is not None
    assert result["content_hash"] == "abc123"


def test_versioning_supersedes_old_row(temp_db):
    import db
    import sqlite3
    from user_profile_columns import build_profile_columns

    user_id = db.get_or_create_user("alice@example.com")
    profile = _make_user_profile()

    db.save_resume_extraction(user_id, profile, build_profile_columns(profile), content_hash="hash_v1")
    db.save_resume_extraction(user_id, profile, build_profile_columns(profile), content_hash="hash_v2")

    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)).fetchall()
        assert len(rows) == 2
        active = [r for r in rows if r["is_active"] == 1]
        inactive = [r for r in rows if r["is_active"] == 0]
        assert len(active) == 1
        assert len(inactive) == 1
        assert inactive[0]["invalidated_reason"] == "superseded"
        assert active[0]["content_hash"] == "hash_v2"
    finally:
        conn.close()


def test_unique_index_prevents_two_active_profiles(temp_db):
    import sqlite3
    import pytest

    conn = sqlite3.connect(temp_db)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("INSERT INTO users (email) VALUES ('test@example.com')")
        user_id = conn.execute(
            "SELECT id FROM users WHERE email = 'test@example.com'"
        ).fetchone()[0]

        conn.execute(
            """INSERT INTO user_profiles
               (user_id, content_hash, schema_version, prompt_version, model_version, is_active, profile_json)
               VALUES (?, 'h1', '1.0', '1.0', 'model', 1, '{}')""",
            (user_id,),
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO user_profiles
                   (user_id, content_hash, schema_version, prompt_version, model_version, is_active, profile_json)
                   VALUES (?, 'h2', '1.0', '1.0', 'model', 1, '{}')""",
                (user_id,),
            )
            conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 2: Run the tests to verify they fail**

```
pytest tests/test_db_user_profiles.py -v -k "get_or_create or get_active or save_resume or versioning or unique_index"
```

Expected: `FAILED` with `AttributeError: module 'db' has no attribute 'get_or_create_user'`

- [ ] **Step 3: Add functions to `src/db.py`** (append after `get_active_job_profile`)

```python
def get_or_create_user(email: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO users (email) VALUES (?)",
            (email,),
        )
        conn.commit()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        return cursor.fetchone()["id"]
    finally:
        cursor.close()
        conn.close()


def get_active_user_profile(user_id: int) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM user_profiles WHERE user_id = ? AND is_active = 1",
        (user_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return dict(row) if row is not None else None


def save_resume_extraction(user_id: int, profile, columns: dict, *, content_hash: str) -> None:
    fixed = {
        "user_id": user_id,
        "content_hash": content_hash,
        "schema_version": profile.meta.schema_version,
        "prompt_version": profile.meta.prompt_version,
        "model_version": profile.meta.model,
        "is_active": 1,
        "profile_json": profile.model_dump_json(),
    }
    all_cols = {**fixed, **columns}
    col_names = list(all_cols.keys())
    col_sql = ", ".join(col_names)
    placeholders = ", ".join(["?"] * len(col_names))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE user_profiles
            SET is_active = 0,
                invalidated_reason = 'superseded'
            WHERE user_id = ? AND is_active = 1
            """,
            (user_id,),
        )
        cursor.execute(
            f"INSERT INTO user_profiles ({col_sql}) VALUES ({placeholders})",
            [all_cols[c] for c in col_names],
        )
        conn.commit()
        logging.info("Saved resume extraction for user_id: %s", user_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
```

- [ ] **Step 4: Run the tests to verify they pass**

```
pytest tests/test_db_user_profiles.py -v
```

Expected: all 8 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/db.py tests/test_db_user_profiles.py
git commit -m "feat(db): add get_or_create_user, get_active_user_profile, save_resume_extraction"
```

---

## Task 5: Add `pypdf` dependency + create `src/prompts/resume_extraction.txt`

**Files:**
- Modify: `requirements.txt`
- Create: `src/prompts/resume_extraction.txt`

Note: The prompt file must exist before `src/pipeline/extract_resume.py` can be imported (it's loaded at module init time).

- [ ] **Step 1: Add `pypdf` to `requirements.txt`**

Append `pypdf` as a new line in `requirements.txt`.

Final `requirements.txt`:
```
python-dotenv
openai
requests
pytest
pytest-cov
pypdf
```

- [ ] **Step 2: Install the new dependency**

```
pip install pypdf
```

Expected: `Successfully installed pypdf-...`

- [ ] **Step 3: Create `src/prompts/resume_extraction.txt`**

```
# prompt_version: 1.0
You extract structured candidate profile data from software engineering resumes.

Return a complete ResumeExtractionResult object matching the schema provided by the caller.

Rules:
- Use only evidence from the provided resume text.
- Do not infer skills, experience, or preferences not shown in the resume.
- If a nullable field cannot be determined, return null.
- If a list field has no evidence, return an empty list.
- Use enum values exactly as defined in the schema.
- `extraction_confidence` must be a float in [0.0, 1.0]. Reduce confidence for sparse, poorly-formatted, or ambiguous resumes.
- `evidence_snippets` should contain short verbatim quotes from the resume supporting key axis scores and role classification.

Field guidance:

`total_years_experience`:
- Sum all non-overlapping professional experience. Internships count at 0.5×.
- Exclude purely academic / coursework time unless it produced deployed software.
- Round to one decimal place.

`current_level`:
- "student": currently enrolled, no substantive professional experience
- "junior": 0–2 years professional, not yet leading independently
- "mid": 2–5 years, owns components independently
- "senior": 5–9 years, owns subsystems, influences design decisions
- "staff": 9+ years or clearly org-wide technical impact
- "principal": distinguished technical leadership, typically >10 years

`primary_role_family`:
Choose the single best fit: "backend" | "frontend" | "fullstack" | "platform" | "ai_ml" | "security" | "product"

Work experience:
- List most recent role first.
- `level_signal` is the inferred seniority for that role, not the candidate's overall level.
- `key_contributions` should be 2–4 bullet points, verbatim or near-verbatim from the resume — evidence only, no paraphrase.
- `years`: approximate duration in years (e.g., a 6-month internship = 0.5).

Career preferences:
- `desired_salary_currency`: "CAD" or "USD" only. Default to "CAD" unless US-specific signals are present.
- If no salary preference is stated, leave desired_salary_min / desired_salary_max as null.
- If desired_seniority is unclear, use "any".

Work authorization:
- `canada` and `us` are booleans indicating legal authorization to work (true = authorized).
- `sponsorship_needed`: true if they require sponsorship, false if they explicitly state they don't, null if unstated.

================================================================================
## Axis scoring rubric
================================================================================

Score 0.0–1.0 for what the candidate demonstrably **can do** based on evidence in the resume.
These are capability scores, not job-fit scores.

### Signal hierarchy (strongest → weakest)

1. **Led / architected / owned end-to-end** — clear technical leadership, design decisions, system ownership → 0.7–1.0
2. **Built independently** — primary contributor on a shipped component → 0.4–0.7
3. **Contributed significantly** — named impact as a team member → 0.25–0.5
4. **Used / familiar with** — coursework, side projects, minor mentions → 0.05–0.25

### Seniority calibration: same technology, different depth

The most common scoring error is treating the presence of a technology as evidence of ownership.

**Backend axis (axis_backend):**

| Resume evidence | Context | Expected score |
|---|---|---|
| "Built REST APIs in Python" | Student project, 0 YOE | ~0.15 |
| "Built REST APIs in Python, deployed to Heroku" | Junior, 1.5 YOE, team service | ~0.35 |
| "Owned Python microservices, led on-call rotation" | Mid, 4 YOE | ~0.60 |
| "Designed distributed Python platform, mentored 4 engineers" | Senior, 8 YOE | ~0.82 |

**Platform axis (axis_platform):**

| Resume evidence | Context | Expected score |
|---|---|---|
| "Deployed app to AWS EC2" | Student, 0 YOE | ~0.10 |
| "Set up CI/CD pipelines with GitHub Actions" | Junior, 2 YOE | ~0.25 |
| "Managed Kubernetes clusters, wrote Terraform modules" | Mid, 4 YOE | ~0.55 |
| "Designed multi-region AWS infrastructure, org-wide IaC standards" | Senior, 7 YOE | ~0.80 |

### Common traps

- Listed technology ≠ owns it. "Used React in one sprint" is not 0.6 frontend.
- Coursework counts at low weight (0.1–0.2 max) unless applied in a substantive role.
- Multi-axis roles: score each axis independently; do not anchor one to another.
- A strong backend candidate can legitimately score moderate frontend — assess independently.

### The 6 axes

**axis_backend**: API design, distributed services, backend languages (Python/Go/Java/Node/Rust), SQL/NoSQL, caching, queuing, microservices.

**axis_frontend**: JS/TS frameworks (React, Vue, Angular), HTML/CSS, browser performance, UI component libraries, design-to-code.

**axis_platform**: Kubernetes, IaC (Terraform, Ansible), cloud platforms at infrastructure level (not merely deploying to), service mesh, platform engineering, container orchestration.

**axis_ai_data**: LLMs, ML models, data pipelines, analytics, streaming, MLOps, RAG, prompt engineering, fine-tuning, model serving.

**axis_security_reliability**: Security engineering, auth systems, observability, on-call, incident response, SRE, compliance, testing rigor (TDD, CI/CD).

**axis_product_ownership**: Working with PMs/designers, end-to-end feature ownership, A/B testing, user-facing metrics, growth engineering, experimentation.

Note: `axis_fullstack_span = round(min(2 * min(axis_backend, axis_frontend), 1.0), 2)` is computed downstream — do NOT include it in output.

================================================================================
## Calibration anchors
================================================================================

Quick reference (ba/fe/pc/ai/sr/ps):

| Candidate | ba | fe | pc | ai | sr | ps |
|---|---|---|---|---|---|---|
| CS student, no internships | 0.12 | 0.08 | 0.05 | 0.10 | 0.05 | 0.10 |
| Junior backend, 1.5 YOE | 0.38 | 0.10 | 0.18 | 0.10 | 0.20 | 0.18 |
| Mid fullstack, 4 YOE | 0.60 | 0.55 | 0.30 | 0.20 | 0.35 | 0.45 |
| Senior platform, 8 YOE | 0.55 | 0.10 | 0.85 | 0.25 | 0.70 | 0.30 |
| Staff AI/ML, 12 YOE | 0.50 | 0.15 | 0.40 | 0.90 | 0.60 | 0.50 |

### Anchor 1: CS student, no internships

**Resume excerpt:** "B.Sc. Computer Science (3rd year). Projects: Expense tracker web app (Flask, PostgreSQL, React). GitHub: small CLI tools in Python."

**Scores:** ba=0.12 / fe=0.08 / pc=0.05 / ai=0.10 / sr=0.05 / ps=0.10

**Rationale:**
- axis_backend=0.12: Flask in a personal project; no team, no scale, no production. Coursework weight only.
- axis_frontend=0.08: React mentioned but clearly secondary; no evidence of UI craft.
- axis_platform=0.05: No cloud infra beyond maybe a basic Heroku deploy; no Kubernetes, no IaC.
- axis_ai_data=0.10: Incidental PostgreSQL; no ML/data engineering signals.
- axis_security_reliability=0.05: No security, observability, or on-call evidence.
- axis_product_ownership=0.10: Personal projects with no PM/design collaboration.

### Anchor 2: Junior backend developer, 1.5 YOE

**Resume excerpt:** "Software Developer at FinTech Startup (18 months). Built REST APIs in Python (FastAPI). Integrated Stripe payment webhooks. Deployed services to AWS EC2. Tech: Python, FastAPI, PostgreSQL, Redis, AWS."

**Scores:** ba=0.38 / fe=0.10 / pc=0.18 / ai=0.10 / sr=0.20 / ps=0.18

**Rationale:**
- axis_backend=0.38: Real production API work as primary contributor; not yet owning a subsystem independently.
- axis_frontend=0.10: No frontend signals; token score.
- axis_platform=0.18: AWS EC2 suggests basic cloud familiarity; no IaC or container orchestration.
- axis_ai_data=0.10: Standard CRUD with PostgreSQL + Redis; no analytics or ML signals.
- axis_security_reliability=0.20: Payment webhook integration implies security awareness; no explicit on-call.
- axis_product_ownership=0.18: Startup context implies PM collaboration; no explicit feature ownership.

### Anchor 3: Mid-level fullstack, 4 YOE

**Resume excerpt:** "Software Engineer at SaaS Company (4 years). Owned user authentication and authorization module (Node.js, React, PostgreSQL). Led migration of frontend from Redux to React Query, reducing latency 40%. Collaborated with product and design on 3 major feature launches."

**Scores:** ba=0.60 / fe=0.55 / pc=0.30 / ai=0.20 / sr=0.35 / ps=0.45

**Rationale:**
- axis_backend=0.60: Owned auth module end-to-end; Node.js with team-level independence. Not yet designing multi-service architecture.
- axis_frontend=0.55: Led a significant frontend migration with measured impact; clear ownership.
- axis_platform=0.30: Implicit cloud deployment; no infra-level ownership evident.
- axis_ai_data=0.20: No ML; standard relational DB use.
- axis_security_reliability=0.35: Auth module ownership implies security design; latency improvement implies observability.
- axis_product_ownership=0.45: Explicit PM/design collaboration with feature launches and impact.

### Anchor 4: Senior platform engineer, 8 YOE

**Resume excerpt:** "Staff Platform Engineer at ScaleUp (3 years). Designed Kubernetes-based deployment platform used by 30 engineering teams. Wrote Terraform modules for multi-region AWS deployment. Set on-call standards and incident runbooks org-wide. Previously: Senior SRE at Enterprise (5 years)."

**Scores:** ba=0.55 / fe=0.10 / pc=0.85 / ai=0.25 / sr=0.70 / ps=0.30

**Rationale:**
- axis_backend=0.55: Strong backend fundamentals implied by platform work; not the primary focus.
- axis_frontend=0.10: No frontend signals.
- axis_platform=0.85: Primary work is Kubernetes platform + Terraform for multi-region; org-wide impact.
- axis_ai_data=0.25: Telemetry and operational data likely but implicit; no explicit ML.
- axis_security_reliability=0.70: SRE background + on-call standards + incident runbooks.
- axis_product_ownership=0.30: Works with engineering teams, not PM/design; delivery-oriented.

### Anchor 5: Staff AI/ML engineer, 12 YOE

**Resume excerpt:** "Staff ML Engineer at AI Company (4 years). Led training and deployment of LLM-based retrieval system serving 10M queries/day. Designed MLOps infrastructure (Kubeflow, Airflow). Published 2 internal papers on fine-tuning. Previously: Senior Data Engineer (4 years), ML Engineer (4 years)."

**Scores:** ba=0.50 / fe=0.15 / pc=0.40 / ai=0.90 / sr=0.60 / ps=0.50

**Rationale:**
- axis_backend=0.50: Strong backend fundamentals for serving infrastructure; not primary focus.
- axis_frontend=0.15: No frontend signals; minor score for API surface awareness.
- axis_platform=0.40: MLOps infrastructure (Kubeflow, Airflow) is platform-adjacent but ML-specific.
- axis_ai_data=0.90: Primary work; LLM training + retrieval + MLOps + published research at scale.
- axis_security_reliability=0.60: 10M query/day system implies significant reliability work.
- axis_product_ownership=0.50: Staff-level role likely involves PM collaboration and product direction.
```

- [ ] **Step 4: Verify the prompt file parses correctly**

```bash
python -c "
import re
with open('src/prompts/resume_extraction.txt') as f:
    content = f.read()
first_line = content.splitlines()[0]
assert first_line.startswith('# prompt_version:'), f'Bad header: {first_line}'
version = first_line.split(':', 1)[1].strip()
assert version == '1.0', f'Expected 1.0, got {version}'
print(f'Prompt version: {version} — OK')
"
```

Expected: `Prompt version: 1.0 — OK`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/prompts/resume_extraction.txt
git commit -m "feat(prompts): add resume extraction prompt with axis rubric and calibration anchors"
```

---

## Task 6: Add `extract_resume_profile()` to `src/integrations/openai_client.py`

**Files:**
- Modify: `src/integrations/openai_client.py`
- Modify: `src/integrations/__init__.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_extract_resume.py` — create the file now)

```python
# tests/test_extract_resume.py

from unittest.mock import MagicMock, patch


def test_extract_resume_profile_raises_on_null_output():
    """MalformedOutputError is raised when output_parsed is None."""
    from integrations import MalformedOutputError
    from integrations.openai_client import extract_resume_profile
    from config.user_profile import ResumeExtractionResult

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
    from config.user_profile import ResumeExtractionResult

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
```

- [ ] **Step 2: Run the test to verify it fails**

```
pytest tests/test_extract_resume.py::test_extract_resume_profile_raises_on_null_output tests/test_extract_resume.py::test_extract_resume_profile_returns_parsed_and_usage -v
```

Expected: `FAILED` with `ImportError` — `extract_resume_profile` not defined yet

- [ ] **Step 3: Add `extract_resume_profile` to `src/integrations/openai_client.py`** (append at end of file)

```python
def extract_resume_profile(
    system_prompt: str,
    resume_text: str,
    *,
    model: str,
    prompt_cache_key: str,
):
    from config.user_profile import ResumeExtractionResult
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
                        "text": f"<resume>\n{resume_text}\n</resume>",
                    }
                ],
            },
        ],
        text_format=ResumeExtractionResult,
        prompt_cache_key=prompt_cache_key,
    )
    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise MalformedOutputError("Model returned no parsed structured output")
    return parsed, response.usage
```

- [ ] **Step 4: Update `src/integrations/__init__.py`** to export the new function

```python
# src/integrations/__init__.py
from .openai_client import (
    MalformedOutputError,
    call_llm,
    extract_job_profile,
    extract_resume_profile,
    get_openai_client,
)

__all__ = [
    "MalformedOutputError",
    "call_llm",
    "extract_job_profile",
    "extract_resume_profile",
    "get_openai_client",
]
```

- [ ] **Step 5: Run the tests to verify they pass**

```
pytest tests/test_extract_resume.py::test_extract_resume_profile_raises_on_null_output tests/test_extract_resume.py::test_extract_resume_profile_returns_parsed_and_usage -v
```

Expected: both `PASSED`

- [ ] **Step 6: Commit**

```bash
git add src/integrations/openai_client.py src/integrations/__init__.py tests/test_extract_resume.py
git commit -m "feat(integrations): add extract_resume_profile() for structured resume extraction"
```

---

## Task 7: Create `src/pipeline/extract_resume.py`

**Files:**
- Create: `src/pipeline/extract_resume.py`
- Modify: `tests/test_extract_resume.py` (append pipeline test)

- [ ] **Step 1: Write the failing test** (append to `tests/test_extract_resume.py`)

```python
# Append to tests/test_extract_resume.py
import json


def _make_fake_extraction_result():
    from config.user_profile import (
        ResumeExtractionResult, ResumeAxes, ResumeSkills,
        WorkExperience, ResumeEducation, CareerPreferences, ResumeWorkAuth,
    )
    return ResumeExtractionResult(
        full_name="Jane Doe",
        total_years_experience=3.0,
        current_level="junior",
        primary_role_family="backend",
        axes=ResumeAxes(
            axis_backend=0.7, axis_frontend=0.1, axis_platform=0.3,
            axis_ai_data=0.2, axis_security_reliability=0.3, axis_product_ownership=0.2,
        ),
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
        evidence_snippets=[{"field": "primary_role_family", "quote": "built REST APIs"}],
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
    original = extract_module._attempt_extraction
    def counting_attempt(text):
        attempt_count["n"] += 1
        return original(text)
    monkeypatch.setattr(extract_module, "_attempt_extraction", counting_attempt)

    extract_module.extract_resume(str(fake_pdf), "jane@example.com")
    captured = capsys.readouterr()
    assert "already up to date" in captured.out
    assert attempt_count["n"] == 0
```

- [ ] **Step 2: Run the test to verify it fails**

```
pytest tests/test_extract_resume.py::test_extract_resume_saves_profile_with_denormalized_columns -v
```

Expected: `FAILED` with `ModuleNotFoundError: No module named 'pipeline.extract_resume'`

- [ ] **Step 3: Create `src/pipeline/extract_resume.py`**

```python
# src/pipeline/extract_resume.py
import hashlib
import os
import sys
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_SRC = os.path.join(_PROJECT_ROOT, 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from pydantic import ValidationError

from config.job_profile import ProfileMeta
from config.user_profile import UserProfile
from db import get_or_create_user, get_active_user_profile, save_resume_extraction
from integrations import extract_resume_profile, MalformedOutputError
from user_profile_columns import build_profile_columns
from utils import log_info


SCHEMA_VERSION = "1.0"
DEFAULT_MODEL = "gpt-4.1-nano"
_MAX_INPUT_CHARS = 60_000


def _read_prompt_and_version(prompt_path: str) -> tuple[str, str]:
    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    first_line = content.splitlines()[0].strip() if content else ""
    if first_line.startswith("# prompt_version:"):
        return content, first_line.split(":", 1)[1].strip()
    return content, "unknown"


_PROMPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'resume_extraction.txt')
_SYSTEM_PROMPT, _PROMPT_VERSION = _read_prompt_and_version(_PROMPT_PATH)
_PROMPT_CACHE_KEY = f"resume:{SCHEMA_VERSION}:{_PROMPT_VERSION}:{DEFAULT_MODEL}"


def _extract_pdf_text(pdf_path: str) -> str:
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _is_current(active: dict, content_hash: str) -> bool:
    return (
        active["content_hash"] == content_hash
        and active["schema_version"] == SCHEMA_VERSION
        and active["prompt_version"] == _PROMPT_VERSION
        and active["model_version"] == DEFAULT_MODEL
    )


def _attempt_extraction(resume_text: str):
    return extract_resume_profile(
        system_prompt=_SYSTEM_PROMPT,
        resume_text=resume_text,
        model=DEFAULT_MODEL,
        prompt_cache_key=_PROMPT_CACHE_KEY,
    )


def _log_usage(user_id: int, usage) -> None:
    if usage is None:
        return
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    details = getattr(usage, "input_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) if details is not None else 0
    pct = 100.0 * cached / input_tokens if input_tokens > 0 else 0.0
    log_info(
        f"resume: user_id={user_id} model={DEFAULT_MODEL} "
        f"input={input_tokens} cached={cached} ({pct:.1f}%)"
    )


def extract_resume(pdf_path: str, email: str) -> None:
    raw_text = _extract_pdf_text(pdf_path)
    if not raw_text.strip():
        print("Warning: no extractable text — scanned or image-only PDF")
        sys.exit(2)

    if len(raw_text) > _MAX_INPUT_CHARS:
        log_info(f"resume: truncating {len(raw_text)} chars to {_MAX_INPUT_CHARS}")
    resume_text = raw_text[:_MAX_INPUT_CHARS]

    content_hash = hashlib.sha256(raw_text.encode()).hexdigest()
    user_id = get_or_create_user(email)

    active = get_active_user_profile(user_id)
    if active and _is_current(active, content_hash):
        log_info(f"resume: user_id={user_id} already up to date, skipping")
        print("Profile is already up to date.")
        return

    extraction_result = None
    usage = None
    last_err: Exception | None = None
    last_kind: str | None = None
    for attempt in (1, 2):
        try:
            extraction_result, usage = _attempt_extraction(resume_text)
            break
        except (MalformedOutputError, ValidationError) as e:
            last_err = e
            last_kind = "malformed_output"
            log_info(f"resume: attempt {attempt} ({last_kind}): {e}")
        except Exception as e:
            last_err = e
            last_kind = "api_error"
            log_info(f"resume: attempt {attempt} ({last_kind}): {e}")

    if extraction_result is None:
        raise RuntimeError(f"Resume extraction failed: {last_kind}: {last_err}")

    profile = UserProfile(
        meta=ProfileMeta(
            schema_version=SCHEMA_VERSION,
            prompt_version=_PROMPT_VERSION,
            model=DEFAULT_MODEL,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        **extraction_result.model_dump(),
    )

    columns = build_profile_columns(profile)
    save_resume_extraction(user_id, profile, columns, content_hash=content_hash)
    _log_usage(user_id, usage)

    if profile.extraction_confidence < 0.5:
        print(f"Warning: low extraction confidence ({profile.extraction_confidence:.2f}) — review profile")

    print(
        f"Extracted: {profile.full_name or 'Unknown'} | "
        f"{profile.current_level} {profile.primary_role_family} | "
        f"confidence={profile.extraction_confidence:.2f}"
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

```
pytest tests/test_extract_resume.py -v
```

Expected: all 4 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/extract_resume.py tests/test_extract_resume.py
git commit -m "feat(pipeline): add extract_resume.py — PDF to UserProfile extraction pipeline"
```

---

## Task 8: Create `src/cli.py`

**Files:**
- Create: `src/cli.py`

- [ ] **Step 1: Create `src/cli.py`**

```python
# src/cli.py
import argparse
import os
import sys

_SRC = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SRC)
for _p in [_SRC, _ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _cmd_ingest_resume(args: argparse.Namespace) -> None:
    if not os.path.isfile(args.pdf_path):
        print(f"Error: PDF not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)
    from pipeline.extract_resume import extract_resume
    extract_resume(args.pdf_path, args.email)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="Job Match Agent CLI",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    resume_parser = subparsers.add_parser(
        "ingest-resume",
        help="Extract structured profile from a PDF resume",
    )
    resume_parser.add_argument("pdf_path", help="Path to the PDF resume file")
    resume_parser.add_argument("--email", required=True, help="Candidate email address")

    args = parser.parse_args(argv)

    if args.command == "ingest-resume":
        _cmd_ingest_resume(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify `--help` works**

```bash
python -m src.cli --help
```

Expected output includes:
```
usage: python -m src.cli ...
  ingest-resume  Extract structured profile from a PDF resume
```

- [ ] **Step 3: Verify error handling for missing PDF**

```bash
python -m src.cli ingest-resume /nonexistent/path.pdf --email test@example.com; echo "exit code: $?"
```

Expected: `Error: PDF not found: /nonexistent/path.pdf` printed to stderr, exit code 1

- [ ] **Step 4: Commit**

```bash
git add src/cli.py
git commit -m "feat(cli): add ingest-resume command — python -m src.cli ingest-resume <pdf> --email <email>"
```

---

## Task 9: Update `src/prompts/extraction.txt` with experience-depth signals

**Files:**
- Modify: `src/prompts/extraction.txt`

The version header changes from `2.2` to `2.3`. The content to add goes in the axis scoring section after the "Signal weighting" block.

- [ ] **Step 1: Update the version header** (line 1 of `extraction.txt`)

Change:
```
# prompt_version: 2.2
```
To:
```
# prompt_version: 2.3
```

- [ ] **Step 2: Insert the experience-depth signals section** after the "Signal weighting" block (after line 101, before "### Common scoring traps to avoid")

```
### Experience-depth signals (v2.3 addition)

**Explicit experience requirement:** If the posting states required years for a domain (e.g., "5+ years of backend experience"), weight that axis upward to reflect expected depth, not just keyword emphasis. "3+ years required" is a depth signal; "experience with" is not.

**Responsibility-framing signal:** The verb choice and scope in responsibilities reveal the seniority depth the role expects. Apply this as a modifier on top of topic signals:

| Tier | Indicator verbs / patterns | Depth weight |
|---|---|---|
| Junior | build, implement, write, assist, contribute to, support | low (0.2–0.4) |
| Mid | develop, maintain, improve, collaborate on design | moderate (0.4–0.6) |
| Senior | design, architect, lead, own, drive, define standards, mentor, make technical decisions | high (0.6–0.85) |
| Staff+ | set technical direction, define roadmap, influence org-wide strategy | very high (0.8–1.0) |

**Same domain, different seniority — expected score difference:**

Backend role, junior framing: "Implement and test backend API features using Python"
→ axis_backend ≈ 0.35–0.50 (work is real but scope is execution, not design)

Backend role, senior framing: "Architect and own the backend platform, establish coding standards, mentor 3–5 engineers"
→ axis_backend ≈ 0.70–0.85 (design ownership + mentorship signals senior depth)

```

- [ ] **Step 3: Add two new calibration anchors** to the table at the bottom (within the Calibration anchors section, after the Visa New Grad row)

In the calibration table, add two rows:
```
| Junior Python Backend (execution framing) | 0.40 | 0.05 | 0.20 | 0.15 | 0.30 | 0.25 | 0.08 |
| Senior Python Backend (architect framing) | 0.80 | 0.05 | 0.40 | 0.20 | 0.65 | 0.45 | 0.10 |
```

After the existing few-shot anchor section, append:

```
## 3. Junior Python Backend (execution framing)

**JD excerpt:** "Implement and test RESTful API endpoints in Python. Contribute to backend services. Fix bugs and write unit tests. 0–2 years experience."

**Scores:** backend 0.40 / frontend 0.05 / platform 0.20 / ai_data 0.15 / security_reliability 0.30 / product_ownership 0.25

**Rationale:**
- `axis_backend = 0.40`: Python backend work is real and primary, but verb framing ("implement", "contribute", "fix") signals execution depth, not design ownership.
- `axis_platform = 0.20`: Backend service deployment implies basic cloud use; no infra signals.
- `axis_security_reliability = 0.30`: Unit tests and API correctness are explicit, but no on-call or security focus.

## 4. Senior Python Backend (architect framing)

**JD excerpt:** "Architect and own our backend platform serving 50M requests/day. Define coding standards and system design patterns. Lead technical design reviews. Mentor 3–5 engineers. 7+ years of backend experience required."

**Scores:** backend 0.80 / frontend 0.05 / platform 0.40 / ai_data 0.20 / security_reliability 0.65 / product_ownership 0.45

**Rationale:**
- `axis_backend = 0.80`: "Architect and own" + explicit 7+ years requirement + system design ownership. Same technology domain as the junior role, but scored 0.40 higher due to depth signals.
- `axis_platform = 0.40`: "50M requests/day" implies significant cloud/infra involvement even without explicit Kubernetes mention.
- `axis_security_reliability = 0.65`: Scale + design ownership + "define standards" implies strong reliability posture.
- `axis_product_ownership = 0.45`: Technical leadership that shapes what gets built, not just how.
```

- [ ] **Step 4: Verify the version bump is picked up**

```bash
python -c "
with open('src/prompts/extraction.txt') as f:
    first_line = f.readline().strip()
assert '2.3' in first_line, f'Expected version 2.3 in: {first_line}'
print(f'Version confirmed: {first_line}')
"
```

Expected: `Version confirmed: # prompt_version: 2.3`

- [ ] **Step 5: Run the full test suite to confirm no regressions**

```
pytest tests/ -v
```

Expected: all tests pass (the version bump will cause `SCHEMA_VERSION` + `_PROMPT_VERSION` tuple to differ from any existing extractions in dev DB, triggering re-extraction on next run — this is correct behavior)

- [ ] **Step 6: Commit**

```bash
git add src/prompts/extraction.txt
git commit -m "feat(prompts): add experience-depth and responsibility-framing signals to axis rubric (v2.3)"
```

---

## Self-Review Checklist

### Spec coverage

| Spec requirement | Covered in task |
|---|---|
| PDF text extraction via `pypdf` | Task 5 (dependency) + Task 7 (`_extract_pdf_text`) |
| Structured LLM extraction to `ResumeExtractionResult` | Task 6 (`extract_resume_profile`) |
| `UserProfile` schema replacing stub in `config/user_profile.py` | Task 1 |
| `user_profiles` SQLite table with versioning pattern | Task 2 |
| `users` table for multi-user support | Task 2 |
| `user_profile_columns.py` projecting to denormalized columns | Task 3 |
| CLI: `python -m src.cli ingest-resume <pdf_path> --email <email>` | Task 8 |
| `src/prompts/resume_extraction.txt` with evidence-weighted rubric | Task 5 |
| Update job-side axis rubric in `extraction.txt` for experience-depth | Task 9 |
| `extract_resume_profile()` in `openai_client.py` | Task 6 |
| `get_or_create_user`, `get_active_user_profile`, `save_resume_extraction` in `db.py` | Task 4 |
| Versioning invariant: re-extraction supersedes old row | Task 4 (test) |
| Unique-index enforcement (at most one active profile per user) | Task 2 (SQL) + Task 4 (test) |
| `extraction_confidence < 0.5` warning, save anyway | Task 7 |
| Empty PDF → `sys.exit(2)` | Task 7 |
| Truncate PDF text > 60k chars | Task 7 |
| `pypdf` in requirements.txt | Task 5 |

All spec requirements have a corresponding task. No gaps found.

### Type consistency check

- `UserProfile.meta` → `ProfileMeta` from `config.job_profile` ✓ (used in Task 1, 7)
- `build_profile_columns(profile: UserProfile) -> dict` keys == `USER_PROFILE_COLUMNS` ✓ (enforced by Task 3 test)
- `save_resume_extraction(user_id, profile, columns, *, content_hash)` → called with keyword `content_hash` in Task 7 ✓
- `_attempt_extraction(resume_text: str)` returns `(ResumeExtractionResult, usage)` ✓ monkeypatched in Task 7 test
- `extract_resume_profile(...)` returns `(parsed, response.usage)` ✓ Task 6

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-07-resume-extraction.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — Fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
