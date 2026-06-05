# Skills Extraction Pipeline — PR4 + PR5 Design

**Date:** 2026-06-04  
**Scope:** PR4 (job_profile_skills population) + PR5 (resume_skills population)  
**Status:** Approved for implementation

---

## 1. Goals

PR3 created the `skills_catalog`, `skill_aliases`, `job_profile_skills`, and `resume_skills` tables and the `canonicalize` / `batch_canonicalize` utilities. PR4 and PR5 wire those tables into the extraction pipelines.

The problem with the existing single-pass LLM extraction: the main call is already doing axes scoring, salary parsing, work auth, education, requirements parsing, and seniority inference. Skills coverage suffers — keywords like "Debugging" that appear repeatedly in the JD are missed because the model is spread thin. The solution is a dedicated second LLM call for each side (job and resume) with a focused prompt.

---

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Skills model shape | Flat `list[SkillEntry]` — no 8 categories | Categories were arbitrary groupings that didn't affect matching logic |
| `group_id` semantics | Nullable integer, local per job profile | Marks OR-alternatives; same `group_id` on same `job_profile_id` = interchangeable skills |
| Job skills LLM input | Raw JD text + extracted `profile_json` | Profile's `must_have_requirements` / `preferred_requirements` are the best importance signal |
| Resume skills LLM input | Raw resume text + extracted `profile_json` | Mining work experience bullets catches skills the flat list misses |
| LLM call isolation | Separate call from `extract_one` | Focused prompt yields better coverage; cleaner versioning |
| Importance on resume | Same `SkillEntry` shape; importance = prominence in resume | Enables future weighted matching; symmetric with job side |
| Stage 2 matching | Pure SQL keyword overlap — no LLM | Sub-10ms per query with existing indexes; fully explainable |

---

## 3. Schema

### Migration: `008_add_group_to_job_profile_skills.sql`

```sql
ALTER TABLE job_profile_skills ADD COLUMN IF NOT EXISTS group_id INTEGER;
ALTER TABLE resume_skills       ADD COLUMN IF NOT EXISTS importance TEXT
    CHECK (importance IN ('must', 'preferred', 'nice'));
```

`group_id` is scoped per `job_profile_id`. Rows with the same `group_id` on the same job profile are OR-alternatives — Stage 2 treats the group as one logical requirement, satisfied if the candidate matches any member. Null means the skill is a standalone AND requirement.

`resume_skills.importance` stores the prominence of the skill in the resume (`must` = heavily demonstrated, `preferred` = projects/supporting roles, `nice` = mentioned once). Not used by Stage 2 today but preserved for future weighted matching.

---

## 4. Data Models

New file: `src/models/skills.py`

```python
from typing import Literal
from pydantic import BaseModel

class SkillEntry(BaseModel):
    skill: str                                        # raw text from LLM
    importance: Literal["must", "preferred", "nice"]
    group_id: int | None = None                       # OR-group; null = standalone AND

class JobSkillScanResult(BaseModel):
    skills: list[SkillEntry]

class ResumeScanResult(BaseModel):
    skills: list[SkillEntry]   # group_id always null; importance = prominence
```

**Two-step flow — `skill` → `skill_id`:**

The LLM emits raw skill names (`skill: str`). After the LLM call, `batch_canonicalize` resolves each to a `skill_id` from `skills_catalog`, auto-inserting unknown skills with `source='auto'`. The DB row stores `(job_profile_id, skill_id, importance, group_id)`. The `skill` string never reaches the DB directly.

For resume `SkillEntry`, `importance` encodes prominence in the resume:
- `must` — skill appears heavily across main work experience
- `preferred` — skill appears in projects or supporting roles
- `nice` — mentioned once or listed in a skills section only

---

## 5. Prompts

### `src/prompts/skills_scan.txt`

Focused job skills extraction. System prompt instructs the LLM to:

- Read the full JD and extract every concrete technical skill and professional concept mentioned or implied (including things like "Debugging", "System Design", "Cross-functional collaboration")
- Use `must_have_requirements` from the profile to tag importance as `must`; use `preferred_requirements` for `preferred`; anything else is `nice`
- Assign the same `group_id` (integer starting at 1) to skills that are explicit OR-alternatives (e.g., "Python or Go", "MySQL or PostgreSQL")
- Standalone skills get `group_id: null`
- Prefer canonical names (e.g., "PostgreSQL" not "Postgres DB"; "Kubernetes" not "k8s")
- Do not invent skills not evidenced in the JD

Input shape:
```
<job_description>{raw jd text}</job_description>
<job_profile>{profile_json with must_have_requirements, preferred_requirements}</job_profile>
```

### `src/prompts/resume_skills_scan.txt`

Focused resume skills extraction. System prompt instructs the LLM to:

- Mine every section: work experience bullets, project descriptions, education, certifications, skills sections
- Tag `importance` by prominence: `must` = heavily demonstrated across multiple roles; `preferred` = demonstrated in projects or one role; `nice` = listed once or briefly mentioned
- `group_id` is always null (candidates don't have OR-alternatives)
- Do not invent skills not evidenced in the resume

Input shape:
```
<resume>{resume text}</resume>
<resume_profile>{profile_json}</resume_profile>
```

---

## 6. Integrations

Two new functions in `src/integrations/openai_client.py`:

```python
def scan_job_skills(
    job_text: str,
    profile_json: str,
    *,
    model: str,
    prompt_cache_key: str,
) -> tuple[JobSkillScanResult, usage]:
    """Structured output call returning JobSkillScanResult."""

def scan_resume_skills(
    resume_text: str,
    profile_json: str,
    *,
    model: str,
    prompt_cache_key: str,
) -> tuple[ResumeScanResult, usage]:
    """Structured output call returning ResumeScanResult."""
```

Both use `client.responses.parse(text_format=<result_model>)` — same pattern as existing extraction calls. The system prompt is cached via `prompt_cache_key`.

---

## 7. Pipeline Orchestration

New file: `src/pipeline/skills_scan.py` (~80 lines)

Owns two public functions:

```python
def populate_job_skills(
    job_profile_id: int,
    job_text: str,
    profile_json: str,
    conn,
) -> None:
    """Call skills LLM → canonicalize → save to job_profile_skills."""

def populate_resume_skills(
    user_profile_id: int,
    resume_text: str,
    profile_json: str,
    conn,
) -> None:
    """Call skills LLM → canonicalize → save to resume_skills."""
```

**Error handling:** If the skills scan LLM call fails (API error or malformed output), log the error and return without raising. The job/resume profile is still valid for Stage 1 axis matching. Stage 2 matching degrades gracefully (empty skill rows → zero keyword score) rather than blocking the extraction.

### Wiring into `extract.py`

`_process_one` calls `populate_job_skills` after `save_extraction` succeeds:

```python
job_profile_id = save_extraction(db_job_id, profile)
populate_job_skills(job_profile_id, job_text, profile.model_dump_json(), conn)
```

`save_extraction` must return the new `job_profiles.id` (currently returns None — this needs to change).

### Wiring into `extract_resume.py`

`_run_extraction_and_save` calls `populate_resume_skills` after `save_resume_extraction` succeeds:

```python
user_profile_id = save_resume_extraction(user_id, profile, columns, content_hash=content_hash)
populate_resume_skills(user_profile_id, resume_text, profile.model_dump_json(), conn)
```

`save_resume_extraction` must return the new `user_profiles.id`.

---

## 8. DB Functions

Two new functions in `src/db.py`:

### `save_job_profile_skills(job_profile_id, entries, conn)`

```python
def save_job_profile_skills(
    job_profile_id: int,
    entries: list[tuple[int, str, int | None]],  # (skill_id, importance, group_id)
    conn,
) -> None:
```

- Deletes existing rows for this `job_profile_id` first (idempotent re-runs)
- Inserts one row per entry into `job_profile_skills`

### `save_resume_skills(user_profile_id, entries, conn)`

```python
def save_resume_skills(
    user_profile_id: int,
    entries: list[tuple[int, str]],  # (skill_id, importance)
    conn,
) -> None:
```

- Deletes existing rows for this `user_profile_id` first
- Inserts one row per entry into `resume_skills`, including `importance`

---

## 9. Stage 2 Matching Query (preview)

The skill overlap score is computed in a single SQL query. The COALESCE collapses OR-groups into one logical requirement using prefixed keys to avoid collisions between `group_id` and `skill_id` namespaces:

```sql
WITH req_groups AS (
    SELECT
        jps.job_profile_id,
        CASE
            WHEN jps.group_id IS NOT NULL THEN 'g' || jps.group_id::text
            ELSE 's' || jps.skill_id::text
        END AS req_key,
        MAX(CASE jps.importance
            WHEN 'must'      THEN 3
            WHEN 'preferred' THEN 2
            ELSE 1
        END) AS weight,
        BOOL_OR(rs.skill_id IS NOT NULL) AS matched,
        ARRAY_AGG(jps.skill_id) FILTER (WHERE rs.skill_id IS NULL)  AS missing_ids,
        ARRAY_AGG(jps.skill_id) FILTER (WHERE rs.skill_id IS NOT NULL) AS matched_ids
    FROM job_profile_skills jps
    LEFT JOIN resume_skills rs
        ON rs.skill_id = jps.skill_id AND rs.resume_id = $user_profile_id
    WHERE jps.job_profile_id = ANY($shortlist)
    GROUP BY jps.job_profile_id, req_key
)
SELECT
    job_profile_id,
    SUM(CASE WHEN matched THEN weight ELSE 0 END)::float
        / NULLIF(SUM(weight), 0)                     AS keyword_score,
    ARRAY_REMOVE(ARRAY_AGG(ARRAY_TO_JSON(missing_ids)), NULL)  AS missing_skill_ids,
    ARRAY_REMOVE(ARRAY_AGG(ARRAY_TO_JSON(matched_ids)), NULL)  AS matched_skill_ids
FROM req_groups
GROUP BY job_profile_id
ORDER BY keyword_score DESC;
```

**LEFT JOIN semantics:** All job skills appear in `req_groups` whether or not the candidate has them. Unmatched skills produce `matched = FALSE`, contributing zero to the numerator but full weight to the denominator. A candidate matching 8 of 10 weighted requirements scores 0.80 and ranks above one scoring 0.50 — no 100% requirement anywhere.

**Performance:** Shortlist of 100 jobs × ~40 skills = 4,000 left-table rows, joined against ~80 resume skills. Sub-10ms with existing indexes. Run on-demand per request; save results to `match_results` for display-layer sorting and pagination.

---

## 10. Matching Pipeline Summary

| Stage | Mechanism | Output |
|-------|-----------|--------|
| 1 | Date filter + hard filters + pgvector axis cosine | ≤100 job_profile_ids |
| 2 | SQL skill overlap (this PR) — weighted fraction, group-aware | Ranked list + keyword_score + matched/missing skills |
| 3 | Optional LLM rerank on top 10–20 (PR10) | Narrative fit score — deferred, not load-bearing |

---

## 11. Tests

### PR4 tests (`tests/test_extract_job_skills.py`)
- After `populate_job_skills`, `job_profile_skills` rows exist for the job profile
- A `must` skill in `must_have_requirements` is stored with `importance='must'`
- Two skills explicitly OR-related share the same non-null `group_id`
- A skill not in `skills_catalog` is auto-inserted with `source='auto'` and referenced by `skill_id`
- `populate_job_skills` is idempotent — calling twice doesn't duplicate rows

### PR5 tests (`tests/test_extract_resume_skills.py`)
- After `populate_resume_skills`, `resume_skills` rows exist for the user profile
- Skills mined from work experience bullets appear (not just from the flat `skills` list)
- Calling twice is idempotent

### Stage 2 query test (`tests/test_match2.py`)
- Candidate with 80% of job's must-have skills scores ~0.8
- OR-group: candidate has one of two OR-alternatives → group counts as matched once (not double-counted)
- `missing_skill_ids` contains the correct unmatched skills
- Job where candidate has all must-skills scores higher than job where must-skills are partially missing

---

## 12. Files Changed

### New files
- `scripts/migrations/008_add_group_to_job_profile_skills.sql`
- `src/models/skills.py`
- `src/prompts/skills_scan.txt`
- `src/prompts/resume_skills_scan.txt`
- `src/pipeline/skills_scan.py`
- `tests/test_extract_job_skills.py`
- `tests/test_extract_resume_skills.py`

### Modified files
- `src/integrations/openai_client.py` — add `scan_job_skills`, `scan_resume_skills`
- `src/db.py` — add `save_job_profile_skills`, `save_resume_skills`; update `save_extraction` and `save_resume_extraction` to return their new row IDs
- `src/pipeline/extract.py` — wire `populate_job_skills` after `save_extraction`
- `src/pipeline/extract_resume.py` — wire `populate_resume_skills` after `save_resume_extraction`
- `tests/test_match2.py` — add Stage 2 query tests
