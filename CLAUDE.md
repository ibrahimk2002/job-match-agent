# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository, the role of the agent is a senior software architect. Perfer simple, direct solutions over enterpsrise over-engineering.
## Project

AI-powered job matching system: ingest job postings (LinkedIn JSONL exports) → extract structured `JobProfile`s once via LLM → match candidates against profiles cheaply via denormalized columns → optional LLM rerank on shortlist. SQLite, single DB file, scale is a few hundred postings. Owner: Ibrahim Khan.

**Core principle**: matching is the product. Extraction exists to feed matching. Never call the LLM per `(candidate, job)` pair — extract once, query denormalized columns many times, reserve LLM for final rerank only.

## Architecture at a glance

Two-layer data model (see `docs/CONTEXT.md` §3 for rationale):

```
job_postings (ingestion: one row per posting, tracks content_hash + profile_status)
    ↓ 1:N (only one is_active=1 per posting)
job_profiles (semantic cache: full profile_json + ~30 denormalized columns)
    ↓
match_results (stage1/stage2 scores, keyed by job_posting_id)
```

- **Ingestion** (`src/pipeline/ingest.py` → `src/db.py::import_jobs_from_jsonl`): discovers `data/reports/*/cleaned_jobs.jsonl`, upserts `job_postings`. `content_hash = SHA-256(title || location || cleaned_description)`. On content change, flips `profile_status` to `stale` (or `missing` if previously failed).
- **Extraction** (`src/pipeline/extract.py` → `src/db.py::save_extraction`): picks jobs where the active profile's `(content_hash, schema_version, prompt_version, model_version)` doesn't match current policy. Calls OpenAI `responses.parse` with `ExtractionResult` as the structured-output schema, wraps in `JobProfile` with `ProfileMeta`, then `profile_columns.build_profile_columns` projects it to all denormalized columns before upsert. Previous active profile is marked `is_active=0, invalidated_reason='superseded'`.
- **Matching** (`src/pipeline/match1.py`, `match2.py`): **current impl is LLM-per-job and commented out in `run.py`**. Target: stage 1 filters on denormalized columns (`role_family`, `seniority`, `work_auth_required`, `salary_*`, `axis_*`) with no LLM; stage 2 reranks top ~100 with LLM. See `docs/TODO_LIST.md` #7.

## Load-bearing modules

| File | Why it matters |
|------|---------------|
| `src/db.py` | All CRUD + `compute_content_hash` + `apply_schema_migrations` (runs every `.sql` in `migrations/` on `init_db`). `JOB_PROFILE_COLUMNS` is the canonical column order for upsert. |
| `src/profile_columns.py` | Projects a `JobProfile` payload to all 30+ `job_profiles` columns. Reads six primary axes directly from `payload["axes"]` (no presets). Computes `axis_fullstack_span = round(min(2*min(backend,frontend), 1.0), 2)` — never from LLM. `salary_*` fields almost always land as `None`. **Upsert invariant:** `build_profile_columns` return keys must equal `JOB_PROFILE_COLUMNS − {"is_active"}` — enforced by `tests/test_profile_columns.py::test_build_columns_keys_match_db_constants`. |
| `src/pipeline/extract.py` | Defines `SCHEMA_VERSION = "1.0"` and `DEFAULT_MODEL`; `prompt_version` parsed from first line of `src/prompts/extraction.txt` (`# prompt_version: X.X`). Those four values are the versioning tuple for re-extraction decisions. |
| `config/job_profile.py` | `JobProfile`, `ExtractionResult`, `ProfileMeta`, `Axes`, `Skills`, `ExperienceRequirements`. `Axes` holds the six primary axis scores (no `axis_fullstack_span`). Both `ExtractionResult` and `JobProfile` carry an `axes: Axes` field. `salary_*`, `work_auth_required`, `degree_required` live in `job_profiles` columns, projected by `profile_columns.py`. |
| `config/user_profile.py` | Pydantic schema for resume side: `ResumeExtractionResult`, `UserProfile`, `ResumeSkills`, `WorkExperience`, etc. `Axes` and `ProfileMeta` are imported from `config.job_profile` (not duplicated). |
| `src/user_profile_columns.py` | Projects a `UserProfile` to 25 denormalized `user_profiles` columns. `USER_PROFILE_COLUMNS` is the canonical list. Same upsert-invariant pattern as `profile_columns.py`. |
| `src/pipeline/extract_resume.py` | Resume extraction pipeline: PDF → text → hash → version check → LLM → save. `SCHEMA_VERSION`, `DEFAULT_MODEL`, `_PROMPT_VERSION` form the versioning tuple. Hash is of truncated content (`resume_text[:60_000]`), not raw file. |
| `src/cli.py` | CLI entry point: `python -m src.cli ingest-resume <pdf> --email <email>`. Handles `sys.exit()` — library code raises exceptions, CLI converts to exit codes. |
| `migrations/001_create_core_schema.sql` | Authoritative schema. `CREATE TABLE IF NOT EXISTS` makes `init_db()` idempotent. There is **no migration-version table** — ordering is purely alphabetical filename. |

## Design guardrails (from `docs/CONTEXT.md` §Guardrails)

1. Do not reintroduce LLM-per-job matching in stage 1.
2. Do not parse `profile_json` during matching — use denormalized columns.
3. Do not merge `job_profiles` back into `job_postings`; they are separate concerns on purpose.
4. Do not treat seniority as a hard filter for early-career users (it's a soft signal unless clearly strict, e.g. "5+ years required").
5. Do not over-normalize into many small tables. Keep full JSON + denormalize the ~20 fields matching actually touches.
6. Stay on SQLite; no vector DB or microservices at current scale.

## How to work here
### Before coding:

Enter plan mode for non-trivial changes. Present the plan and get approval before writing code.
If the request is ambiguous, ask clarifying questions before starting.
Read docs/CONTEXT.md and the relevant migration SQL before proposing schema changes.

### While coding:

Stay in scope. Do not add unrequested features, refactor unrelated code, or create files that weren't asked for.
Functions under ~30 lines, files under ~300 lines, nesting ≤ 3 levels where practical.
Names are self-documenting. Booleans: is_/has_/can_. Functions: verbs. Classes: nouns.
Handle errors at boundaries with meaningful messages. Never swallow exceptions silently.
Use `log_info` from `utils` for all logging in pipeline/library code — not `import logging`. `print()` is reserved for user-facing CLI output.
Library functions raise exceptions; CLI entry points (`src/cli.py`) catch and call `sys.exit()`.

### Before committing:

Show the file list and proposed commit message. Wait for explicit approval before running git commit or git push.
Commit format: type(scope): subject (feat/fix/docs/refactor/test/chore).
Never force-push to main. Never commit secrets, .env, or credentials.

### When stuck:

Stop. Explain the problem, propose 2–3 options with trade-offs, and ask for guidance.

### Running tests:

`pytest tests/ -v` — runs all unit tests. `tests/conftest.py` sets `sys.path` and provides the `temp_db` fixture, which monkeypatches `db._DB_PATH` to a tmpfile and calls `init_db()`. DB tests must use `temp_db`; never reference a real DB path in tests.
Pipeline functions that tests need to monkeypatch (e.g. `_extract_pdf_text`, `_attempt_extraction`) must be module-level — not nested inside other functions.