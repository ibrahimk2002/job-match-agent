# Job Matching Agent — Architecture & Context

**Last updated**: May 2026
**Owner**: Ibrahim Khan
**Status**: Active development. SQLite → Postgres migration in progress.

---

## 1. What This Is and Why It Exists

This is a self-hosted ATS (applicant tracking system) and job-match ranking tool for job seekers. The core problem: a LinkedIn search returns 200 results; maybe 15 are actually worth applying to. Reading them all manually is slow. Commercial tools like Jobscan require pasting jobs one at a time.

This system processes an entire job pipeline in bulk, ranking all postings against a resume with a transparent, auditable score — matching on structured data, not raw text.

**The key insight**: the LLM is expensive, but only needs to run once per job posting. A naive approach (LLM per job per candidate) at 500 jobs × 100 users = 50,000 LLM calls. This system: 500 LLM extraction calls (one-time, cached forever) and 0 LLM calls for any matching query.

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| API layer (planned) | FastAPI (replacing CLI) |
| Database | PostgreSQL + pgvector (migrating from SQLite) |
| LLM | OpenAI API — extraction only, never per match |
| Job data source | LinkedIn JSONL exports |
| Resume source | PDF uploads |

---

## 3. Data Model

### Layer 1 — Ingestion

**`job_postings`** — one row per posting, tracks content changes.
- `content_hash = SHA-256(title || location || cleaned_description)` — detects re-imports with changed content
- `profile_status` — `missing | current | stale | failed` — drives extraction queue
- Never deleted. Content changes flip `profile_status` to `stale`.

**`users`** — one row per registered user, email unique.

### Layer 2 — Semantic Cache

**`job_profiles`** — one active extraction per posting, versioned by `(content_hash, schema_version, prompt_version, model_version)`.
- `profile_json` — full `JobProfile` payload for display and LLM rerank context
- ~30 denormalized scalar columns — used for filtering and scoring without parsing JSON
- `axes_vec vector(6)` — pgvector column for axis cosine similarity in stage 1
- Only one row per posting has `is_active = 1`. Previous versions are archived, not deleted.

**`user_profiles`** — same versioning pattern as `job_profiles`, keyed to `users`.

### Layer 3 — Skills Index

**`skills_catalog`** — controlled vocabulary of canonical skills.
- `canonical` — the authoritative name ("Python", "REST APIs", "PostgreSQL")
- `category` — `hard | soft | other`
- `source` — `auto` (inserted by pipeline) or `curated` (reviewed manually)
- Auto-inserts on unknown skill. Periodic dedup via Levenshtein distance query as needed.

**`skill_aliases`** — lowercased alias strings mapped to `skill_id`.
- Hit only at extraction/canonicalization time, never at query time.
- Lookup chain: exact alias match → case-insensitive canonical match → auto-insert new.

**`job_profile_skills`** — one row per (active job profile × skill). This is the matching inverted index.
- `(job_profile_id, skill_id)` primary key
- `importance: must | preferred | nice` — drives score weighting
- `category` copied from catalog at insert (avoids join in hot path)

**`resume_skills`** — one row per (active user profile × skill).
- Same shape, no `importance` (resume skills are presence-only)

### Layer 4 — Results

**`match_results`** — keyed by `(job_posting_id, user_id)`.
- `stage1_score`, `stage1_detail_json` — filter pass/fail breakdown
- `stage2_score`, `matched_skills_json`, `missing_skills_json` — keyword overlap with explainability
- `stage3_score`, `stage3_reasoning` — LLM rerank output (only top 10–20 ever reach this)

---

## 4. Pipeline

### Ingestion
```
LinkedIn JSONL → ingest.py → job_postings (upsert by source_posting_id)
```
Content hash computed on every import. Changed content → `profile_status = stale`.

### Extraction (job)
```
job_postings WHERE profile_status IN ('missing','stale')
  → LLM (ExtractionResult schema, structured output)
  → JobProfile + ProfileMeta
  → profile_columns.build_profile_columns() → job_profiles row
  → canonicalize skills → job_profile_skills rows
  → previous active profile marked is_active=0, invalidated_reason='superseded'
```
The four-tuple `(content_hash, schema_version, prompt_version, model_version)` determines if re-extraction is needed. If all four match current policy, skip.

### Extraction (resume)
```
PDF → extract_pdf_text() → hash(text[:60_000])
  → version check against active user_profile
  → LLM (ResumeExtractionResult schema)
  → UserProfile
  → user_profile_columns.build_profile_columns() → user_profiles row
  → canonicalize skills → resume_skills rows
```

### Matching

**Stage 1 — Hard filter + axis fit** (pure SQL + pgvector, no LLM):
```sql
SELECT jp.id, (jp.axes_vec <=> up.axes_vec) AS axis_distance
FROM job_profiles jp, user_profiles up
WHERE up.user_id = $user_id
  AND jp.is_active = 1
  AND (jp.work_auth_required IS NULL OR jp.work_auth_required = 0 OR up.work_auth_us = 1)
  AND (jp.degree_required IS NULL OR jp.degree_required <= up.degree_level)
  AND (jp.salary_min IS NULL OR jp.salary_min <= up.desired_salary_max)
  AND (jp.years_min_hard IS NULL OR jp.years_min_hard <= up.total_years_experience)
ORDER BY axis_distance  -- cosine distance; lower = more similar
LIMIT 100;
```
Result: up to 100 shortlisted `job_profile_id`s.

**Stage 2 — Keyword overlap** (pure SQL, no LLM):
```sql
WITH resume AS (SELECT skill_id FROM resume_skills WHERE resume_id = $resume_id),
     totals AS (
         SELECT job_profile_id,
                SUM(CASE importance WHEN 'must' THEN 3 WHEN 'preferred' THEN 2 ELSE 1 END) AS total_weight
         FROM job_profile_skills WHERE job_profile_id = ANY($shortlist)
         GROUP BY job_profile_id
     )
SELECT jps.job_profile_id,
       SUM(CASE jps.importance WHEN 'must' THEN 3 WHEN 'preferred' THEN 2 ELSE 1 END)::float
           / t.total_weight AS keyword_score,
       jsonb_agg(...) FILTER (WHERE r.skill_id IS NOT NULL) AS matched_skills,
       jsonb_agg(...) FILTER (WHERE r.skill_id IS NULL)     AS missing_skills
FROM job_profile_skills jps
JOIN totals t ON t.job_profile_id = jps.job_profile_id
LEFT JOIN resume r ON r.skill_id = jps.skill_id
GROUP BY jps.job_profile_id, t.total_weight
ORDER BY keyword_score DESC;
```
`matched_skills` and `missing_skills` are the Jobscan-style explainability output.

**Stage 3 — LLM rerank** (optional, top 10–20 only):
Loads `profile_json` for each survivor, formats with candidate profile, calls LLM for a final qualitative ranking. Only this stage ever touches the LLM after extraction.

---

## 5. Skills Vocabulary Design

Controlled vocabulary: all extracted skill strings are canonicalized to `skill_id` integers before storage. Matching is always integer comparison — no string scanning at query time.

Why not embeddings for skill matching: ambiguous similarity thresholds, hard to explain to users ("why did PyTorch not match?"), external API dependency at match time. pgvector is reserved for axis cosine only, where the 6-dim vectors are deterministic and the cosine distance is interpretable (role shape similarity).

Why not free-text arrays: `skill_ids INTEGER[]` with GIN index would work for overlap detection, but loses `importance` as a first-class queryable column needed for weighted scoring. The junction table gives importance, category, and the inverted index in one place.

---

## 6. Key Design Decisions

| Decision | Rationale |
|---|---|
| Separate `job_postings` from `job_profiles` | Ingestion and extraction are independent concerns. Content can change without losing extraction history. |
| Keep `profile_json` + denormalized columns | JSON for display/rerank context; scalars for index-backed filtering. Don't query JSON paths during matching. |
| Version extraction by 4-tuple | Any change to content, schema, prompt, or model triggers re-extraction exactly when needed. |
| Only one `is_active=1` profile per posting | Matching always uses the current extraction. History is archived, not deleted. |
| Postgres + pgvector | pgvector needed for axes cosine (stage 1). Postgres unlocks GIN indexes, JSONB, proper FK enforcement. |
| skills_catalog with aliases | Deterministic, explainable, integer-keyed matching. "React.js" and "React" resolve to the same `skill_id`. |
| importance column on job_profile_skills | Must-have/preferred/nice weighting is what makes the score reflect actual JD demands, not just overlap count. |
| No text embeddings for skill matching | Lexical + alias resolution is sufficient and deterministic. Embeddings add ambiguity and an API dependency. |
| Small PRs < 400 lines | Prevents scope creep, makes review tractable, reduces implementation drift. |

---

## 7. Guardrails

1. No LLM calls during stage 1 or stage 2 matching.
2. Never parse `profile_json` during matching — denormalized columns and junction tables only.
3. Never merge `job_profiles` into `job_postings`.
4. Seniority is a soft signal for early-career users unless the JD explicitly states a hard floor (e.g., "5+ years required").
5. No embeddings for skill matching. pgvector is for axis cosine only.
6. No vector DB, no microservices, no managed cloud services that add ops overhead at this scale.
7. PRs stay under ~400 lines. One logical change per PR.

---

## 8. Current State vs Planned

| Area | Current State | Target |
|---|---|---|
| Database | SQLite | **PostgreSQL + pgvector** |
| API layer | CLI (`src/cli.py`) | **FastAPI** |
| Skills storage | `profile_json` only, no junction table | **`job_profile_skills` + `resume_skills`** |
| Axes similarity | Not implemented (columns exist) | **pgvector cosine via `axes_vec`** |
| Stage 1 matching | Commented out in `run.py` | **SQL hard filters + pgvector** |
| Stage 2 matching | LLM-per-job (disabled) | **SQL keyword overlap** |
| Resume skills | 3 of 8 categories in `user_profiles` columns | **Full `resume_skills` junction table** |
| `evidence_snippets` field | In both schemas, never used | **Drop from extraction schemas** |
| `explicit_constraints` field | In job schema, rarely populated | **Drop** |
| `education_requirements` field | Free-text list, never matched | **Drop (degree_required column suffices)** |
