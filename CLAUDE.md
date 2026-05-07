# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AI-powered job matching system: ingest job postings (LinkedIn JSONL exports) → extract structured `JobProfile`s once via LLM → match candidates against profiles cheaply via denormalized columns → optional LLM rerank on shortlist. SQLite, single DB file, scale is a few hundred postings. Owner: Ibrahim Khan.

**Core principle**: matching is the product. Extraction exists to feed matching. Never call the LLM per `(candidate, job)` pair — extract once, query denormalized columns many times, reserve LLM for final rerank only.

## Common commands

```bash
# Install deps (no package manager — requirements only)
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Apply schema migrations (idempotent; auto-applied on any init_db() call too)
python src/migration.py

# One-time backfill of legacy jobs/job_content → job_postings/job_profiles
python scripts/backfills/backfill_legacy_job_tables.py

# Run the pipeline (ingest + extract only; stage1/stage2 are commented out in run.py)
# NOTE: src/main.py currently reads config/user_profile.json which has been deleted
# (WIP migration to config/user_profile.py Pydantic model). Fix the loader before running.
cd src && python main.py

# Tests — pytest.ini is configured but the tests/ directory is currently empty
# (test_db.py, test_config.py, test_utils.py were deleted during the schema redesign).
pytest
pytest tests/test_db.py::TestClass::test_name   # single test, once tests are restored
```

Environment: create `.env` with `OPENAI_API_KEY=...` (see `.env.example`). `src/utils/config.py` raises at import time if it's missing.

## Import convention (important)

Pipeline modules use **src-on-path** imports, not package-relative ones: `from db import ...`, `from pipeline.extract import ...`, `from integrations.openai_client import ...`. `src/pipeline/extract.py` and `src/integrations/openai_client.py` prepend the project root to `sys.path` at import time so `config.job_profile` resolves.

Consequences:
- `python -m src.pipeline.run` **does not work** (bare `from pipeline.extract import` fails under that resolution).
- New code in `src/` should follow the same flat-import style or the pipeline will break.
- `src/db.py` and `src/migration.py` also guard with `try: from .db ...; except ImportError: from db ...` to work both as package and script — mirror this if you add new modules.

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
| `src/profile_columns.py` | Turns an extracted `JobProfile` payload into the 30+ `job_profiles` columns. Radar axes are **currently hardcoded presets per `role_family`** (no real per-job axis extraction yet). `salary_*` fields almost always land as `None`. Work-auth flags are regex'd from `explicit_constraints`. |
| `src/pipeline/extract.py` | Defines `SCHEMA_VERSION = "1.0"` and `DEFAULT_MODEL`; `prompt_version` parsed from first line of `src/prompts/extraction.txt` (`# prompt_version: X.X`). Those four values are the versioning tuple for re-extraction decisions. |
| `config/job_profile.py` | `JobProfile`, `ExtractionResult`, `ProfileMeta`, `Skills`, `ExperienceRequirements`. V1 schema — lacks most matching-critical fields (salary, work auth, degree, axes); those live in `job_profiles` columns instead, computed by `profile_columns.py`. TODO is to promote them into the Pydantic model (`docs/TODO_LIST.md` #1). |
| `config/user_profile.py` | New WIP Pydantic `UserProfile` replacing the old `user_profile.json` (which has been deleted). Not yet wired into `src/cli.py`. |
| `migrations/001_create_core_schema.sql` | Authoritative schema. `CREATE TABLE IF NOT EXISTS` makes `init_db()` idempotent. There is **no migration-version table** — ordering is purely alphabetical filename. |

## Design guardrails (from `docs/CONTEXT.md` §Guardrails)

1. Do not reintroduce LLM-per-job matching in stage 1.
2. Do not parse `profile_json` during matching — use denormalized columns.
3. Do not merge `job_profiles` back into `job_postings`; they are separate concerns on purpose.
4. Do not treat seniority as a hard filter for early-career users (it's a soft signal unless clearly strict, e.g. "5+ years required").
5. Do not over-normalize into many small tables. Keep full JSON + denormalize the ~20 fields matching actually touches.
6. Stay on SQLite; no vector DB or microservices at current scale.

## Doc drift to be aware of

- `docs/CONTEXT.md` §2 ("Current System State") still describes the old `jobs`/`job_content` schema as current. It's been migrated — the live schema is `job_postings` + `job_profiles` per `migrations/001_create_core_schema.sql`. Trust the migration SQL + `src/db.py` over §2 when they disagree. §3–§11 (target architecture, new schema, design decisions) match the code.
- `docs/TODO_LIST.md` is the active roadmap; `docs/CONTEXT.md` §12 "Next Steps" is older and partly superseded.
- `tests/` has been emptied (conftest + test_db/test_config/test_utils deleted). `pytest.ini` remains but `pytest` will find nothing until tests are rebuilt (TODO #10).
