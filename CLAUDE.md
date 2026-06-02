# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository. Role: senior software architect. Prefer simple, direct solutions over enterprise over-engineering.

## Project

AI-powered job matching system: ingest job postings (LinkedIn JSONL exports) → extract structured `JobProfile`s once via LLM → match candidates against profiles cheaply via SQL → optional LLM rerank on shortlist. Owner: Ibrahim Khan.

**Core principle**: matching is the product. Extraction exists to feed matching. Never call the LLM per `(candidate, job)` pair — extract once, query denormalized columns many times, reserve LLM for final rerank only.

**Current migration in progress**: SQLite → PostgreSQL + pgvector. All new schema work targets Postgres. See `docs/TODO_LIST.md` for PR sequence.

## Architecture at a glance

```
job_postings          (ingestion: one row per posting, content_hash + profile_status)
    ↓ 1:N
job_profiles          (semantic cache: profile_json + ~30 denormalized columns + axes_vec)
    ↓ 1:N
job_profile_skills    (inverted index: one row per skill × importance per active profile)
    ↓
match_results         (stage1/stage2/stage3 scores, keyed by job_posting_id + user_id)

users                 (one row per user, email unique)
    ↓ 1:N
user_profiles         (resume extraction cache: same versioning pattern as job_profiles)
    ↓ 1:N
resume_skills         (one row per skill per active resume)

skills_catalog        (canonical skills vocabulary: skill_id, canonical, category, source)
skill_aliases         (alias → skill_id lookup; lowercased strings)
```

**Matching algorithm (three stages):**
- Stage 1 — SQL hard filters on `job_profiles` columns (work_auth, degree, salary bounds) + pgvector cosine on `axes_vec`. No LLM. Returns a shortlist.
- Stage 2 — SQL keyword overlap: `job_profile_skills ⋈ resume_skills`, scored by importance (`must`=3, `preferred`=2, `nice`=1). No LLM. Ranks the shortlist.
- Stage 3 — Optional LLM rerank on top 10–20 jobs only, using `profile_json` for full context.

## Load-bearing modules

| File | Why it matters |
|------|----------------|
| `src/db.py` | All CRUD + `compute_content_hash` + `apply_schema_migrations`. `JOB_PROFILE_COLUMNS` and `USER_PROFILE_COLUMNS` are the canonical column lists for upserts. |
| `src/profile_columns.py` | Projects `JobProfile` payload → all `job_profiles` columns. `build_profile_columns` return keys must equal `JOB_PROFILE_COLUMNS − {"is_active"}`. Enforced by `tests/test_profile_columns.py::test_build_columns_keys_match_db_constants`. |
| `src/user_profile_columns.py` | Projects `UserProfile` → `user_profiles` columns. Same invariant pattern. |
| `src/pipeline/extract.py` | `SCHEMA_VERSION`, `DEFAULT_MODEL`, `prompt_version` from `prompts/extraction.txt` form the four-tuple for re-extraction decisions. |
| `src/pipeline/extract_resume.py` | PDF → text → hash → version check → LLM → save. Hash over `resume_text[:60_000]`. |
| `src/models/job_profile.py` | `JobProfile`, `ExtractionResult`, `Axes`, `Skills`. `Skills` has 8 categories; these feed `job_profile_skills` at extraction time. |
| `src/models/user_profile.py` | `UserProfile`, `ResumeExtractionResult`, `ResumeSkills`. Imports `Axes` and `ProfileMeta` from `job_profile` — not duplicated. |
| `src/cli.py` | CLI entry point. Library code raises exceptions; CLI catches and calls `sys.exit()`. |
| `scripts/migrations/` | Authoritative schema. Applied alphabetically by filename on `init_db()`. No migration-version table — ordering is filename order. |

## Design guardrails

1. Do not reintroduce LLM-per-job matching in stage 1 or 2.
2. Do not parse `profile_json` during matching — use denormalized columns and junction tables.
3. Do not merge `job_profiles` back into `job_postings`; they are separate concerns.
4. Do not treat seniority as a hard filter for early-career users (soft signal unless explicitly strict).
5. Do not over-normalize into many small tables. Denormalize the ~20 fields matching actually touches.
6. Do not use embeddings for skill matching — too ambiguous to tune and explain. pgvector is for axis cosine only.
7. Keep PRs under ~400 lines. One logical change per PR. No mass rewrites.

## How to work here

### Before coding
Enter plan mode for non-trivial changes. Present the plan, get approval, then code.
Read `docs/CONTEXT.md` and relevant migration SQL before proposing schema changes.
Check `docs/TODO_LIST.md` for the current PR in sequence — do not skip ahead.

### While coding
Stay in scope. Do not add unrequested features or refactor unrelated code.
Functions ≤ 30 lines, files ≤ 300 lines, nesting ≤ 3 levels.
Use `log_info` from `utils` for all pipeline/library logging. `print()` for CLI output only.
Library functions raise exceptions; `src/cli.py` catches them and calls `sys.exit()`.

### Before committing
Show the file list and proposed commit message. Wait for explicit approval.
Commit format: `type(scope): subject` (feat/fix/docs/refactor/test/chore).
Never force-push to main. Never commit `.env`, secrets, or credentials.

### Running tests
`pytest tests/ -v` — all unit tests. `tests/conftest.py` provides the `temp_db` fixture (monkeypatches `db._DB_PATH` to a tmpfile, calls `init_db()`). DB tests must use `temp_db`. Never reference a real DB path in tests.
