# Resume Extraction & User Profile Design

**Date:** 2026-05-07
**Author:** Ibrahim Khan
**Status:** Approved — ready for implementation planning

---

## 1. Overview

Add a resume extraction pipeline that mirrors the existing job extraction flow. A user provides a PDF resume; the system extracts structured candidate data into a `UserProfile` stored in a new `user_profiles` SQLite table. The extracted axes and denormalized columns enable symmetric matching against `job_profiles` without per-job LLM calls.

**Design principle:** Extract once per resume version, query denormalized columns many times — same as the job side.

---

## 2. Scope

### In scope
- PDF text extraction via `pypdf`
- Structured LLM extraction to `ResumeExtractionResult` (gpt-4.1-nano, Responses API)
- `UserProfile` schema replacing the current stub in `config/user_profile.py`
- `user_profiles` SQLite table with same versioning pattern as `job_profiles`
- `users` table for multi-user support
- `user_profile_columns.py` projecting `UserProfile` to denormalized columns
- CLI entry point: `python -m src.cli ingest-resume <pdf_path> --email <email>`
- `src/prompts/resume_extraction.txt` with evidence-weighted axis scoring rubric
- Update to job-side axis rubric in `src/prompts/extraction.txt` for experience-depth signals
- `extract_resume_profile()` function in `src/integrations/openai_client.py`

### Out of scope (future)
- S3 resume upload / storage
- Authentication (OAuth, JWT, sessions) — `users` table is the stub
- Stage-1 matching consuming the new user profile (separate feature)
- Multi-resume support per user (currently one active profile per user)

---

## 3. Schema

### `config/user_profile.py` — full replacement

```python
from pydantic import BaseModel

class ResumeAxes(BaseModel):
    axis_backend: float
    axis_frontend: float
    axis_platform: float
    axis_ai_data: float
    axis_security_reliability: float
    axis_product_ownership: float
    # axis_fullstack_span is derived in user_profile_columns.py, not from LLM

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
    years: float                  # duration in years; internships count at 0.5x
    level_signal: str             # "intern"|"junior"|"mid"|"senior"|"staff"|"principal"
    key_contributions: list[str]  # 2–4 bullets, evidence-only

class ResumeEducation(BaseModel):
    degree_level: int    # 0=none/trade, 1=bachelor, 2=master, 3=phd
    fields: list[str]   # e.g. ["Computer Science", "Mathematics"]

class CareerPreferences(BaseModel):
    desired_roles: list[str]
    desired_role_families: list[str]    # e.g. ["backend", "fullstack", "platform"]
    desired_seniority: str              # "junior"|"mid"|"senior"|"staff"|"any"
    desired_work_modes: list[str]       # ["remote", "hybrid", "onsite"]
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
    work_experience: list[WorkExperience]   # most recent first
    education: ResumeEducation
    preferences: CareerPreferences
    work_auth: ResumeWorkAuth
    extraction_confidence: float            # 0.0–1.0
    evidence_snippets: list[dict]           # [{field: str, quote: str}]

class UserProfile(BaseModel):
    meta: ProfileMeta   # imported from config.job_profile — no content_hash field; hash stored separately in DB
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

`ProfileMeta` is reused from `config/job_profile.py` unchanged.

**Why `work_experience` as a list:** The LLM scores axis depth per role and aggregates to the final `axes` scores — a junior role at 1.0 YOE contributes differently than a senior role at 3.0 YOE. The prompt instructs the LLM to weight more recent and senior roles more heavily. `user_profile_columns.py` just reads the final `profile.axes` values; no aggregation happens in Python.

---

## 4. Database

### `migrations/004_add_user_profiles.sql`

```sql
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
    axis_fullstack_span       REAL,   -- derived: round(min(2*min(backend,frontend), 1.0), 2)

    -- top skills (JSON arrays as TEXT, for stage-1 overlap queries)
    skills_languages          TEXT,
    skills_frameworks         TEXT,
    skills_cloud              TEXT,

    -- preferences (candidate-side filters)
    desired_role_families     TEXT,   -- JSON array
    desired_seniority         TEXT,
    desired_work_modes        TEXT,   -- JSON array
    desired_locations         TEXT,   -- JSON array
    desired_salary_min        INTEGER,
    desired_salary_max        INTEGER,
    desired_salary_currency   TEXT,

    -- work eligibility
    work_auth_canada          INTEGER,  -- 0/1
    work_auth_us              INTEGER,  -- 0/1
    sponsorship_needed        INTEGER,  -- 0/1/NULL

    -- education
    degree_level              INTEGER,

    created_at                TEXT DEFAULT (datetime('now'))
);

-- enforce at most one active profile per user at the DB level
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_profiles_active
    ON user_profiles(user_id) WHERE is_active = 1;
```

**Versioning invariant:** A re-extraction is triggered when any of `(content_hash, schema_version, prompt_version, model_version)` differ from the current active row. Previous active row is set `is_active=0, invalidated_reason='superseded'` before the new row is inserted — same pattern as `job_profiles`.

---

## 5. New DB Functions (`src/db.py`)

Three new functions, following existing CRUD style:

- `get_or_create_user(email: str) -> int` — returns `user_id`; inserts if not exists.
- `get_active_user_profile(user_id: int) -> dict | None` — returns the `is_active=1` row or `None`.
- `save_resume_extraction(user_id: int, profile: UserProfile, columns: dict) -> None` — invalidates previous active row, inserts new row with `profile_json=profile.model_dump_json()` and all denormalized columns.

---

## 6. New Modules

### `src/user_profile_columns.py`

Mirrors `src/profile_columns.py`. Projects a `UserProfile` to the flat column dict for DB upsert.

```python
USER_PROFILE_COLUMNS = [
    "full_name", "total_years_experience", "current_level", "primary_role_family",
    "axis_backend", "axis_frontend", "axis_platform", "axis_ai_data",
    "axis_security_reliability", "axis_product_ownership", "axis_fullstack_span",
    "skills_languages", "skills_frameworks", "skills_cloud",
    "desired_role_families", "desired_seniority", "desired_work_modes",
    "desired_locations", "desired_salary_min", "desired_salary_max",
    "desired_salary_currency", "work_auth_canada", "work_auth_us",
    "sponsorship_needed", "degree_level",
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

**Upsert invariant:** `build_profile_columns` return keys must equal `USER_PROFILE_COLUMNS`. Enforced by a test in `tests/test_user_profile_columns.py`.

### `src/pipeline/extract_resume.py`

```python
SCHEMA_VERSION = "1.0"
DEFAULT_MODEL = "gpt-4.1-nano"
_MAX_INPUT_CHARS = 60_000

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'resume_extraction.txt')
_SYSTEM_PROMPT, _PROMPT_VERSION = _read_prompt_and_version(_PROMPT_PATH)
_PROMPT_CACHE_KEY = f"resume:{SCHEMA_VERSION}:{_PROMPT_VERSION}:{DEFAULT_MODEL}"

def extract_resume(pdf_path: str, email: str) -> None:
    # 1. Load PDF text
    raw_text = _extract_pdf_text(pdf_path)
    if not raw_text.strip():
        print("Warning: no extractable text — scanned or image-only PDF")
        sys.exit(2)

    # 2. Truncate if needed
    resume_text = raw_text[:_MAX_INPUT_CHARS]

    # 3. Content hash + user
    content_hash = hashlib.sha256(raw_text.encode()).hexdigest()
    user_id = get_or_create_user(email)

    # 4. Version check — skip if already current
    active = get_active_user_profile(user_id)
    if active and _is_current(active, content_hash):
        log_info(f"resume: user_id={user_id} already up to date, skipping")
        print("Profile is already up to date.")
        return

    # 5. LLM extraction with retry (2 attempts, mirrors extract.py)
    result, usage = _attempt_extraction(resume_text)

    # 6. Build UserProfile
    profile = UserProfile(
        meta=ProfileMeta(
            schema_version=SCHEMA_VERSION,
            prompt_version=_PROMPT_VERSION,
            model=DEFAULT_MODEL,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        **result.model_dump(),
    )

    # 7. Project + save (content_hash passed separately — not in ProfileMeta)
    columns = build_profile_columns(profile)
    save_resume_extraction(user_id, profile, columns, content_hash=content_hash)

    # 8. Log usage
    _log_usage(user_id, usage)
    print(
        f"Extracted: {profile.full_name or 'Unknown'} | "
        f"{profile.current_level} {profile.primary_role_family} | "
        f"confidence={profile.extraction_confidence:.2f}"
    )
```

**`_extract_pdf_text`** uses `pypdf.PdfReader`, concatenates page text with a newline separator.

---

## 7. OpenAI Client (`src/integrations/openai_client.py`)

New function alongside `extract_job_profile`:

```python
def extract_resume_profile(
    system_prompt: str,
    resume_text: str,
    *,
    model: str,
    prompt_cache_key: str,
):
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
                "content": [{"type": "input_text", "text": f"<resume>\n{resume_text}\n</resume>"}],
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

---

## 8. CLI (`src/cli.py`)

```
python -m src.cli ingest-resume <pdf_path> --email <email>
```

- `--email` required; maps to `user_id` via `get_or_create_user`.
- Validates PDF path exists before calling extraction.
- Prints one-line summary on success.
- `sys.exit(2)` on empty PDF text (scanned/image PDF).
- Future: replace `--email` with `--user-id` once auth is wired.

---

## 9. Prompt Design (`src/prompts/resume_extraction.txt`)

Mirrors `extraction.txt` structure: version header → rules → field rubrics → axis scoring rubric with calibration anchors → output format.

### Axis scoring rubric (candidate-side)

Score 0.0–1.0 for what the candidate demonstrably **can do**, not what they've been exposed to.

**Signal hierarchy (strongest → weakest):**
- led / architected / owned end-to-end
- built independently (solo or primary contributor)
- contributed significantly (named impact, team member)
- used / familiar with (coursework, side project, minor contribution)

**Seniority calibration — same technology, different depth:**

| Evidence | Axis score |
|---|---|
| "Built REST APIs in Python" — student project, 0 YOE | ~0.15 backend |
| "Built REST APIs in Python" — junior, team service, 2 YOE | ~0.35 backend |
| "Owned Python microservices, led on-call" — 5 YOE | ~0.65 backend |
| "Designed distributed Python platform, mentored 4 engineers" — 8 YOE | ~0.85 backend |

**Common traps:**
- Listed technology ≠ owns it. "Used React in one sprint" is not 0.6 frontend.
- Coursework counts at low weight (0.1–0.2 max) unless applied in a real role.
- Multi-axis roles: score each axis independently; do not anchor one to the other.

**Calibration anchors:** 4–5 worked examples (student, junior, mid, senior, staff). Each shows a resume snippet + expected axis scores + rationale.

### Job-side axis rubric update (`src/prompts/extraction.txt`)

Two new signals added to the existing axis scoring section:

**Experience-depth signal (explicit):** If the posting states required years for a domain ("5+ years of backend experience"), weight that axis upward to reflect expected depth, not just emphasis.

**Responsibility-framing signal (implicit):** Verb choice and scope in responsibilities reveal expected seniority depth:

| Tier | Indicator verbs / patterns | Depth weight |
|---|---|---|
| Junior | build, implement, write, assist, contribute to, support | low (0.2–0.4) |
| Mid | develop, maintain, improve, collaborate on design | moderate (0.4–0.6) |
| Senior | design, architect, lead, own, drive, define standards, mentor, make technical decisions | high (0.6–0.85) |
| Staff+ | set technical direction, define roadmap, influence org-wide strategy | very high (0.8–1.0) |

Update calibration anchors to show two postings for the same domain — one junior-framed, one senior-framed — with different scores and rationale.

---

## 10. Error Handling

| Condition | Behaviour |
|---|---|
| PDF path does not exist | CLI prints error, exits 1 |
| PDF has no extractable text | print warning, `sys.exit(2)` |
| PDF text > 60k chars | truncate to 60k, log warning |
| OpenAI API error | propagate with message; no silent swallow |
| Malformed structured output | retry once; on second failure log and raise |
| `extraction_confidence < 0.5` | print warning, save anyway; user decides |

---

## 11. Testing

- `tests/test_user_profile_columns.py` — upsert invariant: `build_profile_columns` keys match `USER_PROFILE_COLUMNS`
- `tests/test_extract_resume.py` — mock OpenAI call; assert `UserProfile` is saved and denormalized columns are populated
- `tests/test_db_user_profiles.py` — uses `temp_db` fixture; assert versioning invariant (re-extraction supersedes old row), unique-index enforcement, `get_or_create_user` idempotency

---

## 12. Files Changed / Created

| Action | Path |
|---|---|
| Replace | `config/user_profile.py` |
| New | `migrations/004_add_user_profiles.sql` |
| New | `src/user_profile_columns.py` |
| New | `src/pipeline/extract_resume.py` |
| New | `src/prompts/resume_extraction.txt` |
| Update | `src/integrations/openai_client.py` — add `extract_resume_profile()` |
| Update | `src/db.py` — add `get_or_create_user`, `get_active_user_profile`, `save_resume_extraction` |
| Update | `src/cli.py` — add `ingest-resume` command |
| Update | `src/prompts/extraction.txt` — add experience-depth signals to axis rubric |
| New | `tests/test_user_profile_columns.py` |
| New | `tests/test_extract_resume.py` |
| New | `tests/test_db_user_profiles.py` |
