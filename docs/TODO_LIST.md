# Job Matching Agent — TODO & PR Sequence

> **Working principle**: one PR per row. Each PR should be < 400 lines and independently deployable.
> Start a session by reading this file + `CLAUDE.md`. Read `docs/CONTEXT.md` only if you need architectural rationale.

---

## ✅ Completed

- Core schema: `job_postings`, `job_profiles`, `users`, `user_profiles`, `match_results`
- Ingestion pipeline: `ingest.py` → `job_postings`
- Job extraction pipeline: `extract.py` → `job_profiles` + denormalized columns
- Resume extraction pipeline: `extract_resume.py` → `user_profiles`
- Versioning tuple: `(content_hash, schema_version, prompt_version, model_version)`
- Content-hash change detection
- Active profile logic (`is_active = 1`, superseded on re-extract)
- CLI entry point (`src/cli.py`)

---

## 🔴 In Sequence — Work Through These in Order

### PR 1 — Schema cleanup: drop overengineered fields

**Goal**: Remove fields that cost LLM tokens and storage but are never used in matching or display. Shrink the extraction prompt. No behavior change.

**Changes:**
- `src/models/job_profile.py`: remove `eligible_countries`, `eligible_regions`, `explicit_constraints` from `ExtractionResult` and `JobProfile`
- `src/prompts/extraction.txt`: remove corresponding prompt instructions
- `tests/`: update any fixtures or assertions referencing removed fields

**DoD**: `pytest tests/ -v` passes. Extraction still runs against a sample job and produces a valid `JobProfile` without the dropped fields. `profile_json` no longer contains them.

---

### PR 2 — Postgres migration

**Goal**: Swap the database driver and schema dialect from SQLite to PostgreSQL. No logic changes — purely infrastructure. Every subsequent PR builds on this.

**Changes:**
- `requirements.txt`: add `psycopg2-binary` (or `asyncpg`), add `pgvector`
- `src/db.py`: replace `sqlite3` with `psycopg2`. Update connection string to read `DATABASE_URL` from env. Replace `?` placeholders with `%s`. Replace `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY` in any inline DDL.
- `scripts/migrations/005_postgres_baseline.sql`: Postgres-dialect version of full schema. Add `CREATE EXTENSION IF NOT EXISTS vector;`
- `tests/conftest.py`: update `temp_db` fixture to spin up a test Postgres connection (use `DATABASE_URL` env var pointing to a test DB, or use `pytest-postgresql`)
- `.env.example`: add `DATABASE_URL=postgresql://user:pass@localhost:5432/jobmatch`

**DoD**: `pytest tests/ -v` passes against Postgres. Full pipeline (`ingest → extract → resume ingest`) runs end-to-end on Postgres. SQLite files are no longer referenced in code.

---

### PR 3 — Skills catalog tables

**Goal**: Create the controlled vocabulary infrastructure. No extraction changes yet — just the schema and the canonicalization utility that later PRs will call.

**Changes:**
- `scripts/migrations/006_skills_catalog.sql`: create `skills_catalog`, `skill_aliases`, `job_profile_skills`, `resume_skills` (see `docs/CONTEXT.md §3` for exact schema)
- `src/skills.py` (new file, ≤ 80 lines): `canonicalize(skill_text: str, conn) -> int` — does alias lookup → canonical lookup → auto-insert. `batch_canonicalize(skills: list[str], conn) -> list[int]`.
- `tests/test_skills.py`: unit tests for `canonicalize` — known alias resolves correctly, unknown skill auto-inserts, case-insensitive match works, duplicate calls return same `skill_id`

**DoD**: Tests pass. `canonicalize("react.js", conn)` and `canonicalize("React", conn)` return the same `skill_id` after seeding one alias. `canonicalize("some-novel-skill-xyz", conn)` inserts a new row with `source='auto'`.

---

### PR 4 — Populate job_profile_skills at extraction

**Goal**: During job extraction, after saving `job_profiles`, canonicalize the extracted `skills` object and insert rows into `job_profile_skills` with correct `importance` tags.

**Context**: `JobProfile.skills` has 8 categories (`languages`, `frameworks`, `cloud`, `databases`, `devops`, `ai_ml`, `other_tools`, `concepts`). `must_have_requirements` and `preferred_requirements` are sentence lists — the LLM needs to emit skill-level importance tags. Two approaches:
- **Option A** (recommended): Update extraction prompt to emit `must_skills: list[str]` and `preferred_skills: list[str]` as flat lists alongside the existing `skills` object. Skills not in either list are tagged `nice`. This avoids parsing sentences.
- **Option B**: Parse `must_have_requirements` sentences in Python to find skill names. Fragile.

**Changes (Option A):**
- `src/models/job_profile.py`: add `must_skills: list[str]` and `preferred_skills: list[str]` to `ExtractionResult` and `JobProfile`
- `src/prompts/extraction.txt`: add instructions for `must_skills` and `preferred_skills`
- `src/pipeline/extract.py`: after `save_extraction`, call `populate_job_profile_skills(job_profile_id, profile, conn)`
- `src/db.py`: add `populate_job_profile_skills(job_profile_id, profile, conn)` — iterates all skills, looks up each in catalog, inserts `job_profile_skills` row with importance derived from `must_skills`/`preferred_skills` membership
- `tests/test_extract.py`: assert that after extraction, `job_profile_skills` rows exist with correct importance tags

**DoD**: Extract a sample job. Query `SELECT * FROM job_profile_skills WHERE job_profile_id = X` returns rows with `must` importance for skills in `must_skills` and `preferred` for `preferred_skills`. `pytest tests/ -v` passes.

---

### PR 5 — Populate resume_skills at resume extraction

**Goal**: Mirror PR 4 for the resume side. After resume extraction, canonicalize all `ResumeSkills` categories and insert into `resume_skills`.

**Changes:**
- `src/pipeline/extract_resume.py`: after `save_resume_extraction`, call `populate_resume_skills(user_profile_id, profile, conn)`
- `src/db.py`: add `populate_resume_skills(user_profile_id, profile, conn)` — iterates all 8 `ResumeSkills` categories, canonicalizes each, inserts `resume_skills` rows
- `src/user_profile_columns.py`: add missing skill columns to `USER_PROFILE_COLUMNS` — `skills_databases`, `skills_devops`, `skills_ai_ml`, `skills_other_tools`, `skills_concepts` (currently only languages/frameworks/cloud are stored)
- `tests/test_extract_resume.py`: assert `resume_skills` rows exist after resume extraction

**DoD**: Run resume extraction on a sample PDF. `SELECT COUNT(*) FROM resume_skills WHERE resume_id = X` returns > 0. Skills from `ai_ml` and `databases` categories are present. Tests pass.

---

### PR 6 — Add axes_vec and pgvector index

**Goal**: Populate the `axes_vec vector(6)` column on `job_profiles` and `user_profiles` from existing axis scalar columns. This enables stage 1 cosine similarity without any extraction changes.

**Changes:**
- `scripts/migrations/007_add_axes_vec.sql`: `ALTER TABLE job_profiles ADD COLUMN axes_vec vector(6); ALTER TABLE user_profiles ADD COLUMN axes_vec vector(6);` + HNSW index on each
- `src/profile_columns.py`: compute and include `axes_vec` in `build_profile_columns` return dict (as a Python list `[backend, frontend, platform, ai_data, security, product]`)
- `src/user_profile_columns.py`: same
- `src/db.py` or a migration script: backfill `axes_vec` for all existing  rows from scalar columns
- `tests/test_profile_columns.py`: add assertion that `axes_vec` is present and has 6 elements

**DoD**: All existing `job_profiles` and `user_profiles` rows have non-null `axes_vec`. The HNSW index is created. `pytest tests/ -v` passes.

---

### PR 7 — Stage 1 matching: hard filters + axis cosine

**Goal**: Implement stage 1 as a pure SQL query. No LLM. Returns up to 100 `job_profile_id`s for a given user.

**Changes:**
- `src/pipeline/match1.py`: rewrite `run_stage1(user_id, conn) -> list[int]`. Single SQL query: hard filters (`work_auth`, `degree_required`, `salary`, `years_min_hard`) + `ORDER BY axes_vec <=> user_axes_vec LIMIT 100`.
- `src/db.py`: add `save_stage1_results(results: list[dict], conn)` — upserts `match_results` with `stage1_score`, `stage1_detail_json`
- `scripts/migrations/008_match_results_v2.sql`: add `user_id` FK to `match_results` if not present; add `stage1_detail_json JSONB`, `stage2_score`, `matched_skills_json JSONB`, `missing_skills_json JSONB`, `stage3_score`, `stage3_reasoning`; drop `stage1_reasoning` (no LLM in stage 1)
- `tests/test_match1.py`: test hard filter logic — job requiring work auth is excluded for candidate without it; job with axes far from candidate scores lower than close match

**DoD**: `run_stage1(user_id, conn)` returns a list of job_profile_ids sorted by axis similarity. Hard-filter test cases pass. No LLM calls anywhere in stage 1. `pytest tests/ -v` passes.

---

### PR 8 — Stage 2 matching: keyword overlap

**Goal**: Score the stage 1 shortlist by keyword overlap using the junction tables. Returns ranked results with explainability output.

**Changes:**
- `src/pipeline/match2.py`: rewrite `run_stage2(user_id, shortlist: list[int], conn) -> list[dict]`. Single SQL query joining `job_profile_skills ⋈ resume_skills`, scoring by importance weight, aggregating `matched_skills` and `missing_skills` as JSONB. See `docs/CONTEXT.md §4` for exact query shape.
- `src/db.py`: add `save_stage2_results(results: list[dict], conn)` — updates `match_results` rows
- `tests/test_match2.py`: test scoring — job with 3 must-skills all matched scores higher than job with 3 must-skills partially matched; `missing_skills` array contains the correct unmatched skills with their importance

**DoD**: `run_stage2` returns ranked list with `keyword_score`, `matched_skills`, `missing_skills` per job. A job where the resume has all must-have skills scores > 0.8. Tests pass.

---

### PR 9 — FastAPI scaffold

**Goal**: Replace CLI as primary interface. Thin HTTP layer over existing pipeline functions. CLI stays working.

**Changes:**
- `src/main.py`: FastAPI app with lifespan (DB pool init/close), router includes
- `src/api/` (new dir): `routes/jobs.py`, `routes/resumes.py`, `routes/matches.py`
- Initial endpoints:
  - `POST /ingest` — trigger ingestion (background task)
  - `POST /resumes` — upload PDF, trigger resume extraction (background task)
  - `POST /match` — trigger stage 1 + 2 for a user (background task)
  - `GET /matches?user_id=X&limit=50` — return ranked results with skill explainability
- `requirements.txt`: add `fastapi`, `uvicorn`, `python-multipart`
- `tests/test_api.py`: basic smoke tests for each endpoint (not full integration)

**DoD**: `uvicorn src.main:app` starts without errors. `POST /resumes` with a PDF returns 202. `GET /matches?user_id=1` returns JSON with `keyword_score`, `matched_skills`, `missing_skills` per job.

---

## 🟠 After Core Matching Works

- **PR 10** — Stage 3 optional LLM rerank: load `profile_json` for top 10–20, call LLM, store `stage3_score` + `stage3_reasoning`
- **PR 11** — Multi-source ingestion: add second job source beyond LinkedIn JSONL
- **PR 12** — Frontend scaffold: React + TypeScript app consuming FastAPI
- **PR 13** — Auth: API key header middleware, user scoping on all queries
- **PR 14** — Hosting setup: Postgres on Neon/Supabase/Railway, environment config, deployment

---

## ⚪ Deliberately Deferred

- No scraping / automated job pulling until manual ingestion pipeline is stable
- No semantic embeddings for skill matching (decision: lexical + aliases is sufficient and more explainable)
- No multi-tenant access control until single-user flow is stable and tested
