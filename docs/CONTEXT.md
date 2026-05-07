# Job Matcher System: Context & Architecture

**Date**: April 2026  
**Project Status**: Database redesign in planning phase  
**Scale**: ~200-400 job postings, single SQLite database

---

## Design Philosophy (Recent Iteration Context)

This project recently underwent a major conceptual shift based on the following realizations:

1. **Matching is the core product, not extraction**
   - Extraction exists only to support matching
   - The schema must be designed around matching, not parsing

2. **LLMs should NOT be used per job**
   - Current system calls LLM per job → too expensive
   - New system:
     - Extract once
     - Match cheaply many times
     - Use LLM only for final reranking

3. **Structured data > raw text at match time**
   - Matching should never re-read job descriptions
   - Matching operates ONLY on `job_profiles` + `candidate_profile`

4. **Hard filters must be explicit and queryable**
   - Work authorization, sponsorship, location, degree
   - These must be columns, not buried in JSON

5. **Seniority and YOE are soft signals (early-career bias)**
   - New grads can match mid roles depending on context
   - Only treat as hard when clearly strict (e.g., 5+ years)

6. **Requirement logic matters (AND vs OR)**
   - “React AND TypeScript” ≠ “Python OR C++”
   - Future schema must support requirement grouping logic

7. **We are optimizing for speed, cost, and iteration**
   - KISS over perfect normalization
   - SQLite is sufficient for now
   - Avoid premature vector DB or microservices

---

## 1. Project Summary

This is an AI-powered job matching system that connects candidate profiles (from resumes) to job postings (from LinkedIn and other sources) using a combination of:
- Hard filtering (work authorization, location, degree requirements)
- Deterministic scoring (role family, seniority, experience, salary)
- Semantic similarity (radar-chart axis alignment, embeddings)
- Optional LLM reranking (for final candidate ranking)

**Core goal**: Enable candidates to find relevant jobs without repeatedly reprocessing job descriptions or running expensive LLM calls for every candidate-job comparison.

**Why it matters**: Naive matching would require an LLM call for every (candidate, job) pair. With 500 candidates and 500 jobs, that's 250,000 LLM calls. The redesign caches extraction once per job and uses cheap filtering + scoring for matching.

---

## 2. Current System State

### What exists now:

**Database (SQLite)**:
- `jobs` table: posting metadata (title, company, location, url, posted_date, source_file)
- `job_content` table: raw description text, `profile_json` (extracted JobProfile), extraction status, promotion columns (role_family, seniority, work_mode, extraction_confidence)
- `match_results` table: stage1 and stage2 scores for each job
- `user_actions` table: user application tracking (unused)

**Code modules**:
- `src/db.py`: database connection, CRUD operations, all table access methods
- `src/pipeline/ingest.py`: discovers JSONL files, imports jobs
- `src/pipeline/extract.py`: LLM extraction loop; stores profile_json
- `src/pipeline/match1.py`: stage-1 matching (currently LLM-based)
- `src/pipeline/match2.py`: stage-2 reranking (currently LLM-based)
- `src/integrations/openai_client.py`: LLM API wrapper
- `config/job_profile.py`: Pydantic schemas (JobProfile, ExtractionResult, ProfileMeta)
- `src/prompts/`: extraction.txt, match1.txt, match2.txt (LLM prompt templates)

**Data**:
- `data/reports/`: subdirectories per batch (swe_toronto_week, swe_us_week, swe_canada_week)
  - Each contains: `cleaned_jobs.jsonl`, `cleaned_jobs.csv`, `cleanup_report.json`
- `data/job_matcher.db`: SQLite database
- `config/job_profile.py`: user profile template (unstructured JSON)

### What the current system does:

1. **Ingest**: Reads `cleaned_jobs.jsonl` files, inserts into `jobs` + `job_content` with status='pending'
2. **Extract**: Fetches pending jobs, calls OpenAI with extraction prompt, stores full `profile_json` + promoted columns
3. **Match Stage 1**: Fetches extracted jobs, deserializes profile_json, calls LLM with user + job profile, records stage1_score/decision
4. **Match Stage 2**: For jobs that passed stage 1, calls LLM again with deeper reasoning, records stage2_score/decision

**Current problem**: Both matching stages call the LLM per job. This is expensive and unnecessary because the profile is already extracted.

---

## 3. Core Architectural Concept

The system is built on a **separation of concerns**:

```
┌─────────────────────┐
│  Ingestion Layer    │  Source-of-truth: raw + cleaned job postings
│  (job_postings)     │  Answers: "what posting exists?" "did content change?"
└─────────────────────┘
          ↓
┌─────────────────────┐
│ Semantic Layer      │  Matching-ready extracted structure
│ (job_profiles)      │  Answers: "what kind of role?" "what signals matter?"
└─────────────────────┘
          ↓
┌─────────────────────┐
│  Candidate Profile  │  User resume parsed into structure
│  (candidate_profile)│
└─────────────────────┘
          ↓
┌─────────────────────┐
│   Matching Engine   │  Compare candidate vs job_profiles
│                     │  Filter → Score → Shortlist → Rerank
└─────────────────────┘
```

**Key insight**: Never re-extract a job. Extract once, cache the result, compare the cache against candidate profiles repeatedly.

---

## 4. Data Flow: End-to-End Pipeline

### Step 1: Ingestion
```
LinkedIn CSV export (.json or .jsonl)
    ↓
ingest.py: discover_report_jsonl_files() finds all cleaned_jobs.jsonl files
    ↓
ingest.py: ingest_data() calls db.import_jobs_from_jsonl() for each file
    ↓
db.py: import_jobs_from_jsonl() parses JSONL, inserts into jobs + job_content
    ↓
New rows created with:
  - jobs: source_id (UNIQUE), url, title, company, location, posted_date, source_file
  - job_content: job_id (FK), raw_text (cleaned description), extraction_status='pending'
```

### Step 2: Extraction
```
extraction.py: extract_job_data() calls db.get_pending_extraction()
    ↓
db.py: returns rows where extraction_status='pending' + raw_text IS NOT NULL
    ↓
For each pending job:
  - Read extraction prompt from src/prompts/extraction.txt (contains prompt_version comment)
  - Call openai_client.extract_job_profile(job_text, system_prompt) → ExtractionResult
  - Wrap in JobProfile with ProfileMeta (schema_version, prompt_version, model, generated_at)
  - Call db.save_extraction() to store profile_json + denormalized columns
    ↓
db.py: UPDATE job_content SET:
  - profile_json = JobProfile.model_dump_json()
  - extraction_status = 'done'
  - role_family, seniority, work_mode, extraction_confidence (from profile)
  - extracted_at = CURRENT_TIMESTAMP
```

### Step 3: Matching Stage 1
```
match1.py: run_stage1_matching(user_profile) calls db.get_jobs_for_stage1()
    ↓
db.py: returns rows where extraction_status='done' AND no match_results row exists
    ↓
For each job:
  - Deserialize profile_json
  - Format user profile + job profile as JSON strings
  - Substitute into match1.txt prompt template
  - Call openai_client.call_llm(prompt) → { score, decision, reasoning }
  - Call db.save_stage1_result(job_id, score, decision, reasoning)
    ↓
match_results row created with stage1_score, stage1_decision, stage1_reasoning
```

### Step 4: Matching Stage 2
```
match2.py: run_stage2_matching(user_profile) calls db.get_jobs_for_stage2()
    ↓
db.py: returns rows where stage1_decision='advance' AND stage2_score IS NULL
    ↓
For each job:
  - Deserialize profile_json again
  - Format prompt similar to stage 1
  - Call openai_client.call_llm(prompt) → { score, decision, reasoning }
  - Call db.save_stage2_result(job_id, score, decision, reasoning)
    ↓
match_results row updated with stage2_score, stage2_decision, stage2_reasoning
```

### Step 5: Results
```
db.get_top_matches(limit=10) returns jobs ordered by stage2_score DESC
```

---

---

## Final Matching Flow (Target Architecture)

1. User submits resume
2. System builds `candidate_profile` (once)

3. Stage 1: Filtering
   - Query `job_profiles` using denormalized columns
   - Remove jobs failing hard filters

4. Stage 2: Deterministic Scoring
   - Score remaining jobs using:
     - role match
     - skill overlap
     - seniority fit
     - salary fit
     - radar-axis similarity
   - Return top ~50–100 jobs

5. Stage 3: Reranking (optional LLM)
   - Run LLM only on top 15–20 jobs
   - Optimize for interview likelihood

6. Return top 5 jobs

---

**Key principle**:
No raw job text is used during matching.
Only `job_profiles` are used.

---

## 5. File Structure & Responsibilities

```
job-matcher/
├── src/
│   ├── db.py                          # Database layer: all CRUD operations
│   │                                   # Tables: jobs, job_content, match_results, user_actions
│   ├── cli.py                         # Command-line interface (unused in current pipeline)
│   ├── main.py                        # Entry point (unused)
│   ├── pipeline/
│   │   ├── ingest.py                  # Discover JSONL files, import_jobs_from_jsonl()
│   │   ├── extract.py                 # LLM extraction loop, ProfileMeta assembly
│   │   ├── match1.py                  # Stage-1 matching (currently LLM-based)
│   │   ├── match2.py                  # Stage-2 reranking (currently LLM-based)
│   │   └── run.py                     # Orchestrator: calls init_db(), then stages sequentially
│   ├── integrations/
│   │   └── openai_client.py           # OpenAI API calls, structured output, error handling
│   ├── prompts/
│   │   ├── extraction.txt             # System prompt for extraction (includes prompt_version)
│   │   ├── match1.txt                 # Prompt template for stage-1 scoring
│   │   └── match2.txt                 # Prompt template for stage-2 scoring
│   └── utils/
│       ├── config.py                  # Config loading (job_profile.json)
│       └── utils.py                   # Logging, helpers
├── config/
│   ├── job_profile.py                 # Pydantic models: JobProfile, ExtractionResult, ProfileMeta, Skills, ExperienceRequirements
│   └── job_profile.json               # User profile template (unstructured JSON with roles, skills, work_auth, etc.)
├── data/
│   ├── reports/                       # Batch directories (swe_toronto_week, swe_us_week, swe_canada_week)
│   │   └── {batch}/
│   │       ├── cleaned_jobs.jsonl     # Cleaned job descriptions (ingestion source)
│   │       ├── cleaned_jobs.csv       # Same data as CSV
│   │       └── cleanup_report.json    # Metadata about cleaning process
│   ├── job_matcher.db                 # SQLite database (created at runtime)
│   └── ...
├── logs/
│   └── job_matcher.log                # Pipeline execution logs
├── tests/
│   ├── conftest.py                    # Pytest fixtures (temp database setup)
│   ├── test_config.py                 # Config tests
│   ├── test_db.py                     # Database CRUD tests
│   └── test_utils.py                  # Utility tests
├── pytest.ini                         # Pytest configuration
├── requirements.txt                   # Python dependencies
└── docs/
    └── CONTEXT.md                     # This file
```

---

## 6. Key Concepts

### Job Profile

A structured representation of what a job is offering. Currently defined in `config/job_profile.py` as `JobProfile` Pydantic model:

```python
class JobProfile(BaseModel):
    job_id: str
    normalized_title: str
    role_family: Literal["backend", "frontend", "full_stack", "data", "ml", "devops", "qa", "mobile", "unknown"]
    role_subtype: str | None
    seniority: Literal["intern", "new_grad", "junior", "mid", "senior", "staff", "principal", "unknown"]
    employment_type: Literal["full_time", "contract", "internship", "temporary", "unknown"]
    work_mode: Literal["remote", "hybrid", "onsite", "unknown"]
    location_scope: str | None
    summary: str
    must_have_requirements: list[str]
    preferred_requirements: list[str]
    responsibilities: list[str]
    skills: Skills  # languages, frameworks, cloud, databases, devops, ai_ml, other_tools, concepts
    experience_requirements: ExperienceRequirements  # years_min, years_max, level_signal
    education_requirements: list[str]
    domain_signals: list[str]  # e.g., "machine-learning", "kubernetes"
    explicit_constraints: list[str]
    extraction_confidence: float  # 0.0–1.0
    evidence_snippets: list[EvidenceSnippet]  # quotes from original text
    profile_meta: ProfileMeta  # schema_version, prompt_version, model, generated_at
```

**Current limitation**: This schema is too generic for matching. It lacks:
- Denormalized filtering columns (years_min_soft vs years_min_hard, salary_min/max, salary_tier, etc.)
- Radar-chart axes (backend/frontend/platform/ai/ownership/collaboration)
- Work authorization metadata
- Sponsorship availability
- Degree requirement clarity
- Region/country eligibility
- Salary period/currency

**JobProfileV2** (target redesign) will add these denormalized columns to `job_profiles` table for efficient querying.

### Candidate Profile

A structured representation of what a candidate is seeking, extracted from a resume. Not yet implemented in code, but conceptually:

```python
class CandidateProfile(BaseModel):
    candidate_id: str
    preferred_role_family: list[str]  # ["backend", "full_stack"]
    preferred_seniority: list[str]    # ["junior", "mid", "senior"]
    preferred_work_mode: list[str]    # ["remote", "hybrid"]
    required_work_auth: bool | None   # can work without sponsorship? can work with?
    degree_required: bool
    years_experience: int
    preferred_salary_min: int | None
    preferred_salary_max: int | None
    salary_currency: str
    skills: dict[str, list[str]]      # domain → [skill1, skill2, ...]
    skill_interests: list[str]        # want to learn these
    geographic_preferences: list[str] # ["Toronto", "remote", "USA"]
    radar_axes: dict[str, float]      # backend: 0.7, frontend: 0.3, ...
```

**Matching principle**: Compare candidate profile dimensions against job profile dimensions. Hard filters come first (work auth, location, degree); then scoring (role family match, seniority, salary, radar axes).

### Denormalized Columns

**What**: Fields that live both in full JSON and as separate scalar columns in the database.

**Why**: 
- **Speed**: Matching needs to filter and score on 20+ fields. Parsing JSON on every comparison is slow.
- **Indexing**: SQLite indexes work on columns, not JSON paths. Denormalized fields enable multi-column indexes.
- **Debugging**: Seeing `role_family='backend'` in logs is clearer than `json_extract(profile_json, '$.role_family')`.
- **Analytics**: Dashboard queries, radar-chart generation, and reporting work naturally with columns.
- **Avoids**: Matching runs on EVERY job for EVERY user.

**Example denormalized fields in job_profiles table**:
- `role_family` (TEXT) — used in every stage-1 filter
- `salary_min`, `salary_max` (INTEGER) — used to check against candidate budget
- `work_auth_required` (INTEGER NULL) — hard filter
- `years_min_hard` (INTEGER) — hard filter for experienced candidates
- `axis_backend`, `axis_frontend`, etc. (REAL 0.0–1.0) — used for radar-chart similarity scoring

**Retention rule**: Full JSON profile stays in `profile_json` for flexibility and audit. Frequently queried fields are copied to scalar columns. If a field is queried rarely, keep it in JSON only to save space.

### Embeddings (Planned)

Not yet implemented, but conceptually: convert job profiles and candidate profiles into vector embeddings, then use cosine similarity for fast approximate matching.

**Use case**: Stage 1 can filter candidates down to the top-100 job matches by embedding similarity before applying hard filters.

**Why not now**: Current scale (few hundred jobs) does not justify embedding infrastructure. Add after basic matching works.

### Why Separate Ingestion from Semantic Data

**Ingestion table** (`job_postings`):
- Records what was imported and when
- Tracks content changes via `content_hash`
- Stores raw + cleaned text (for re-extraction if needed)
- One row per posting; multiple imports of the same posting update one row

**Semantic table** (`job_profiles`):
- Records what we extracted and when
- One row per extraction; historical rows are kept
- Only one row per posting is marked `is_active = 1` (current)
- Versioned by content_hash + schema_version + prompt_version + model_version

**Benefit**: Can re-extract a job with a new prompt/model without deleting old extractions. Can track extraction quality over time. Can ingest new postings or reimport changed ones without touching extraction state.

### Hard Filters vs Ranking Features

This is a critical distinction for matching.

**Hard Filters (binary eligibility)**
Used to REMOVE jobs:
- work_auth_required
- sponsorship_available
- location_scope / country_scope
- work_mode (if strict)
- degree_required (if strict)
- years_min_hard

If a job fails a hard filter → it is excluded.

---

**Ranking Features (scored signals)**
Used to RANK jobs:
- role_family match
- seniority proximity
- skills overlap
- salary alignment
- radar-axis similarity
- domain alignment

These should NEVER hard-reject unless explicitly required.

---

**Design rule**:
All hard filters MUST be denormalized columns.

---

## 7. Current Database Schema

### Tables

#### `jobs`
```sql
CREATE TABLE jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   TEXT NOT NULL UNIQUE,
    url         TEXT,
    title       TEXT,
    company     TEXT,
    location    TEXT,
    posted_date TEXT,
    source_file TEXT,
    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

#### `job_content`
```sql
CREATE TABLE job_content (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id                INTEGER NOT NULL UNIQUE,
    raw_text              TEXT,
    extraction_status     TEXT NOT NULL DEFAULT 'pending',  -- pending, done, failed
    extraction_error      TEXT,
    extracted_at          DATETIME,
    profile_json          TEXT,  -- full JobProfile as JSON string
    role_family           TEXT,  -- denormalized from profile_json
    seniority             TEXT,  -- denormalized from profile_json
    work_mode             TEXT,  -- denormalized from profile_json
    extraction_confidence REAL,  -- denormalized from profile_json
    FOREIGN KEY (job_id) REFERENCES jobs(id)
)
```

#### `match_results`
```sql
CREATE TABLE match_results (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id           INTEGER NOT NULL UNIQUE,
    stage1_score     REAL,
    stage1_decision  TEXT,  -- advance, reject, etc.
    stage1_reasoning TEXT,
    stage2_score     REAL,
    stage2_decision  TEXT,
    stage2_reasoning TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
)
```

#### `user_actions`
```sql
CREATE TABLE user_actions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     INTEGER NOT NULL,
    status     TEXT,
    notes      TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
)
```

### Limitations of Current Schema

1. **Artificial split**: jobs + job_content should be one table; they are always 1:1.
2. **Denormalization inconsistency**: Only 4 fields are denormalized (role_family, seniority, work_mode, extraction_confidence). Missing: years, salary, work auth, sponsorship, seniority levels, etc.
3. **Extraction state muddled**: extraction_status, extraction_error, and extracted_at live in job_content but should be tracked separately for each extraction version.
4. **No content-hash tracking**: Cannot detect if a posting was re-imported with different content.
5. **No version awareness**: If extraction prompt changes, there is no way to know which profiles were extracted with which prompt.
6. **profile_json is unvalidated**: No database-level enforcement that profile_json matches JobProfile schema.
7. **No indexes**: Queries like `extraction_status = 'done'` will full-table scan (OK at 300 rows, breaks at 10k).

---

## 8. Proposed Database Redesign

### Why redesign?

Current matching is expensive:
- Every (candidate, job) comparison calls the LLM twice (stage 1 + stage 2).
- Extraction and matching are conflated; extraction state lives in job_content.
- No version tracking; unclear if profiles are current or stale.
- Denormalized columns are incomplete; stage-1 matcher still deserializes JSON per job.

### New schema (target)

Two core tables: `job_postings` (ingestion) + `job_profiles` (semantic cache).

#### `job_postings` (merged ingestion table)
```sql
CREATE TABLE job_postings (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    source_system           TEXT NOT NULL,  -- "linkedin"
    source_posting_id       TEXT NOT NULL,
    source_url              TEXT,
    title_raw               TEXT,
    company_raw             TEXT,
    location_raw            TEXT,
    posted_date_raw         TEXT,
    source_file             TEXT,
    source_batch            TEXT,
    source_metadata_json    TEXT,          -- spillover for CSV fields
    cleaned_description_text TEXT,         -- text used for extraction
    raw_description_text    TEXT,          -- original if different
    content_hash            TEXT,          -- SHA-256(title_raw || location_raw || cleaned_text)
    first_seen_at           DATETIME NOT NULL,
    last_seen_at            DATETIME NOT NULL,
    imported_at             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_content_changed_at DATETIME,
    profile_status          TEXT NOT NULL DEFAULT 'missing',  -- missing, current, stale, failed, blocked
    last_profile_attempt_at DATETIME,
    last_profile_error      TEXT,
    is_deleted_at_source    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (source_system, source_posting_id)
)
```

**Purpose**: Canonical posting snapshot. Answers: "what posting exists?", "did content change?", "is extraction current?".

#### `job_profiles` (semantic extraction cache)
```sql
CREATE TABLE job_profiles (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_posting_id          INTEGER NOT NULL,
    content_hash            TEXT NOT NULL,
    schema_version          TEXT NOT NULL,  -- "2.0"
    prompt_version          TEXT NOT NULL,  -- "1.0"
    model_version           TEXT NOT NULL,  -- "gpt-4-turbo"
    extracted_at            DATETIME NOT NULL,
    extraction_confidence   REAL NOT NULL DEFAULT 0.5,
    is_active               INTEGER NOT NULL DEFAULT 0,  -- 0/1; only one per posting
    invalidated_at          DATETIME,
    invalidated_reason      TEXT,
    profile_json            TEXT NOT NULL,  -- full JobProfileV2 as JSON
    
    -- Denormalized filtering/scoring columns (must-have for stage 1)
    normalized_title        TEXT NOT NULL,
    role_family             TEXT NOT NULL,  -- backend, frontend, full_stack, data, ml, devops, qa, mobile, unknown
    role_subtype            TEXT,
    seniority               TEXT NOT NULL,  -- intern, new_grad, junior, mid, senior, staff, principal, unknown
    employment_type         TEXT NOT NULL,  -- full_time, contract, internship, temporary, unknown
    work_mode               TEXT NOT NULL,  -- remote, hybrid, onsite, unknown
    location_scope          TEXT,
    work_auth_required      INTEGER,        -- NULL=unknown, 0=not required, 1=required
    sponsorship_available   INTEGER,        -- NULL=unknown, 0=no, 1=yes
    degree_required         INTEGER,        -- NULL=unknown, 0=no, 1=yes
    years_min_soft          INTEGER,        -- inferred/flexible minimum
    years_min_hard          INTEGER,        -- explicit stated minimum
    salary_min              INTEGER,
    salary_max              INTEGER,
    salary_currency         TEXT,           -- ISO 4217 code
    salary_period           TEXT,           -- annual, hourly, monthly, project
    salary_tier             INTEGER,        -- ordinal bucket (1=entry, 2=mid, 3=senior, 4=principal)
    
    -- Radar-chart axes (for job-shape similarity)
    axis_backend            REAL NOT NULL,  -- 0.0–1.0
    axis_frontend           REAL NOT NULL,
    axis_platform           REAL NOT NULL,
    axis_ai_data            REAL NOT NULL,
    axis_ownership          REAL NOT NULL,
    axis_collaboration      REAL NOT NULL,
    
    -- Optional fields (can add later)
    eligible_countries_json TEXT,
    eligible_regions_json   TEXT,
    
    FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
    UNIQUE (job_posting_id, content_hash, schema_version, prompt_version, model_version)
)
```

**Purpose**: Matching-ready extracted structure. Answers: "what kind of role?", "what signals matter?", "is this extraction current?".

### Migration path

1. Create both new tables alongside old ones.
2. Backfill `job_postings` from `jobs` + `job_content` (one row per job).
3. Backfill `job_profiles` from extracted `job_content` rows with `extraction_status='done'`.
4. Validate counts, hashes, and schema compatibility.
5. Update `src/db.py` to use new queries.
6. Update `src/pipeline/ingest.py`, `extract.py`, `match1.py`, `match2.py` to work with new tables.
7. Test a full pipeline iteration.
8. Deprecate old tables (rename to `jobs_deprecated`, `job_content_deprecated`).

---

## 9. Matching Pipeline: Current vs Target

### Current (expensive, per-job LLM)
```
Stage 1:
  For each extracted job:
    - Deserialize profile_json
    - Format user_profile + job_profile as JSON
    - Call LLM with match1.txt prompt
    - Record stage1_score, stage1_decision

Stage 2:
  For each job passing stage 1:
    - Deserialize profile_json again
    - Format user_profile + job_profile as JSON
    - Call LLM with match2.txt prompt
    - Record stage2_score, stage2_decision
```

**Cost**: (num_jobs * LLM_call_cost) × 2 stages = very expensive for 100 candidates × 500 jobs.

### Target (cached extraction + cheap filtering + selective rerank)
```
Stage 1 (Deterministic filtering + scoring):
  For each active job_profile:
    - Read denormalized columns directly (no JSON parsing)
    - Apply hard filters:
      - work_auth_required matches candidate
      - sponsorship_available matches candidate
      - work_mode matches candidate preference
      - location_scope matches candidate preference
      - degree_required matches candidate
      - years_min_hard <= candidate.years_experience
      - salary_min, salary_max overlaps with candidate budget
    - Compute score from:
      - role_family match (1.0 if match, 0.0 if mismatch)
      - seniority match (0.0–1.0 based on distance)
      - salary_tier match
      - radar-axis cosine similarity: dot(candidate.axes, job.axes)
    - Record stage1_score, stage1_decision='advance' if score > threshold

Stage 2 (Selective LLM reranking):
  For each job passing stage 1 (top-100 by stage1_score):
    - Optionally read profile_json for deeper semantic signals
    - Call LLM for final reranking if needed
    - Record stage2_score, stage2_decision
```

**Cost**: No LLM calls for stage 1. Stage 2 LLM calls only on shortlist (e.g., top 100 jobs, not 500).

---

## 10. Current Problems & Limitations

### Matching is too expensive
- Both stages call LLM per job.
- Extraction is redundant; profile_json is regenerated for each match.
- No caching or intermediate results.

### Schema is too generic
- JobProfile lacks filtering dimensions needed for matching.
- No explicit work authorization, sponsorship, degree, salary, seniority logic.
- Cannot do deterministic filtering without JSON parsing.

### Extraction is not aligned with matching
- Extraction produces JobProfile, but matching doesn't use most fields.
- Denormalized columns (role_family, seniority, work_mode) exist but are incomplete.
- No radar-chart axes or axis-based scoring.

### No versioning or re-extraction control
- If extraction prompt changes, no way to know which profiles are stale.
- If LLM model is upgraded, profiles are outdated but still marked "done".
- Cannot re-extract a job without deleting old result or manually managing versions.

### No content-change detection
- If LinkedIn re-imports a job with different description, no way to detect it.
- Extraction is blindly skipped because status='done' is permanent.
- No `content_hash` to track what content the extraction was based on.

### Database is not optimized for retrieval
- No indexes on common query patterns (extraction_status, role_family, seniority, etc.).
- Full-table scans on every stage-1 match.
- JSON parsing on every profile_json deserialize.

### Missing: candidate profile extraction
- Resumes are not yet parsed into CandidateProfile schema.
- No candidate-to-job comparison logic.
- No implementation of hard filters or radar-axis scoring.

### Missing: embeddings
- No vector similarity search.
- No semantic fallback if categorical match fails.

---

## 11. Design Decisions Made

### 1. Separate ingestion from semantic data
**Decision**: One table for postings, one for profiles.  
**Rationale**: Ingestion and extraction are separate concerns. Posting metadata rarely changes; extraction can be re-done. One table per concern keeps logic clear.

### 2. Keep full JSON + denormalize frequently used fields
**Decision**: Store full `profile_json` AND scalar denormalized columns.  
**Rationale**: JSON provides flexibility; scalars enable fast queries and indexing. Do not over-normalize; denormalize only what is queried often.

### 3. Version extraction by content_hash + schema + prompt + model
**Decision**: Track four-tuple (content_hash, schema_version, prompt_version, model_version).  
**Rationale**: Extraction is valid only if all four match desired policy. If any changes, profile is stale. Enables safe re-extraction without ambiguity.

### 4. Mark only one profile active per posting
**Decision**: `is_active = 1` for exactly one `job_profiles` row per job_posting_id.  
**Rationale**: Matching uses only active profiles. Historical profiles are archived, not deleted. Enables rollback and audit.

### 5. Use deterministic stage-1 filtering/scoring
**Decision**: Stage 1 uses no LLM; it filters and scores on denormalized columns and embeddings (optional and depends on job > ~2000).  
**Rationale**: Fast, reproducible, explainable. LLM reserved for final reranking on shortlist.

### 6. Use SQLite, not PostgreSQL or cloud DB
**Decision**: Stick with SQLite for now.  
**Rationale**: Scale is few hundred jobs. Single file, no ops overhead. Can migrate later if needed.

### 7. Do not implement candidate profile extraction or matching yet
**Decision**: Schema is designed for it, but code is not written.  
**Rationale**: Finalize job ingestion + extraction first. Add candidate matching when job pipeline is stable.

---

## 12. Next Steps (Priority Order)

### Week 1: Finalize design
- [ ] Review and approve new `job_postings` and `job_profiles` table schemas
- [ ] Define exact extraction payload for content_hash (title + location + cleaned_description_text)
- [ ] Enumerate enum values for role_family, seniority, employment_type, work_mode, profile_status
- [ ] Define radar-axis extraction logic and scoring algorithm
- [ ] Update `config/job_profile.py` to include all denormalized fields (JobProfileV2)

### Week 2: Write migration
- [ ] Create `migration.py` script that:
  - Creates both new tables
  - Backfills job_postings from jobs + job_content
  - Backfills job_profiles from extracted job_content rows
  - Validates row counts, hashes, uniqueness constraints
  - Generates detailed report
- [ ] Test migration on copy of job_matcher.db
- [ ] Verify rollback safety

### Week 2-3: Refactor database layer
- [ ] Update `src/db.py`:
  - Keep old functions for safety; add new variants that use new tables
  - Implement `import_jobs_from_jsonl_v2()` → inserts into job_postings
  - Implement `get_pending_extraction_v2()` → queries based on profile_status and version mismatch
  - Implement `save_extraction_v2()` → inserts into job_profiles with version metadata
  - Add helpers: `get_active_job_profile()`, `mark_profile_stale()`, `get_posts_needing_extraction()`
- [ ] Write tests for new DB functions (especially versioning logic)

### Week 3: Refactor matching pipeline
- [ ] Update `src/pipeline/match1.py`:
  - Replace JSON deserialization with direct denormalized column queries
  - Implement hard filter logic (work_auth, sponsorship, work_mode, location, degree, years, salary)
  - Implement deterministic scoring (role_family, seniority, salary_tier, axis similarity)
- [ ] Update `src/pipeline/match2.py`:
  - Accept shortlist from stage 1
  - Load profile_json only for candidates advancing to rerank

### Week 4: Validation and cutover
- [ ] Run migration on test database
- [ ] Compare old and new read results (should be identical for now)
- [ ] Run full pipeline with new schema
- [ ] Verify extraction, stage 1, stage 2 all work
- [ ] If stable, rename old tables to `_deprecated`
- [ ] Update tests to reflect new schema

### Later: Enhancements
- [ ] Implement candidate profile extraction from resumes
- [ ] Implement hard-filter matching logic (candidate vs job filters)
- [ ] Add embeddings for semantic similarity
- [ ] Implement radar-axis scoring
- [ ] Build dashboards for job analytics and radar charts
- [ ] Add multi-source ingestion (Glassdoor, Indeed, etc.)
- [ ] Implement vector database (e.g., pgvector in PostgreSQL if scale demands)

---

## 13. How to Use This Document

**For the next agent**:
1. Read sections 1–3 for project context.
2. Read section 4 to understand the current data flow.
3. Read section 6 for file structure and where to find code.
4. Read sections 7–9 to understand current vs target DB design.
5. Read section 10 for current problems.
6. Read section 12 for immediate next steps.
7. Use section 11 (design decisions) as reference when making tradeoffs.

**For running the current system**:
```bash
cd /path/to/job-matcher
source .venv/bin/activate
python -m src.pipeline.run
```

**For accessing the database**:
```python
from src.db import get_db_connection
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM jobs")
print(cursor.fetchone())
```

---

## 14. Key Files to Reference

| File | Purpose | Status |
|------|---------|--------|
| `config/job_profile.py` | JobProfile schema definition | Needs update to JobProfileV2 |
| `src/db.py` | Database CRUD layer | Needs refactor to new tables |
| `src/pipeline/extract.py` | LLM extraction loop | Needs update for job_profiles table |
| `src/pipeline/match1.py` | Stage-1 matching | Needs complete rewrite (deterministic) |
| `src/pipeline/match2.py` | Stage-2 reranking | Needs refactor (shortlist only) |
| `src/prompts/extraction.txt` | Extraction prompt | Needs expansion for all JobProfileV2 fields |
| `tests/test_db.py` | DB tests | Needs complete rewrite for new schema |

---

## Guardrails for Future Development

The following mistakes must be avoided:

1. ❌ Do NOT reintroduce LLM-per-job matching
2. ❌ Do NOT parse JSON repeatedly during matching
3. ❌ Do NOT merge job_profiles back into ingestion table
4. ❌ Do NOT treat seniority as a strict filter for early-career users
5. ❌ Do NOT over-normalize into many small tables prematurely

Preferred approach:
- Keep ingestion simple
- Keep profiles structured + denormalized
- Keep matching fast and mostly deterministic
- Use LLM only where it adds real value

---

**Last updated**: April 2026  
**Owner**: Ibrahim Khan
**Next review**: After initial implementation phase
