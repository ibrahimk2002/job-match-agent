# Job Match Agent

<p align="center">
  <strong>AI-powered job matching that turns scraped jobs and resumes into ranked, explainable matches.</strong>
</p>

<p align="center">
  <em>Extract once. Match fast. No LLM per pair.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-in%20development-blue" />
  <img src="https://img.shields.io/badge/database-PostgreSQL%20%2B%20pgvector-336791" />
  <img src="https://img.shields.io/badge/python-3.12-yellow" />
  <img src="https://img.shields.io/badge/license-Proprietary-red" />
</p>

---

## Product Preview

> UI mocks showing the intended product experience. The CLI pipeline is live — the web interface is a planned next step.

<table>
  <tr>
    <td align="center"><strong>Onboarding</strong><br /><sub>Resume upload + preferences</sub><br /><br /><img src="./public/Upload.png" alt="Onboarding screenshot" width="100%" /></td>
    <td align="center"><strong>Match Results</strong><br /><sub>Ranked jobs + explanations</sub><br /><br /><img src="./public/Matches.png" alt="Results screenshot" width="100%" /></td>
    <td align="center"><strong>Skill Analysis</strong><br /><sub>Axis breakdown + skill gaps</sub><br /><br /><img src="./public/Skills Analysis.png" alt="Skill Analysis screenshot" width="100%" /></td>
  </tr>
</table>

---

## Overview

Job Match Agent ingests LinkedIn job postings, extracts structured `JobProfile` data once via LLM, and matches candidates against those profiles cheaply via SQL and pgvector. The LLM is never called per candidate-job pair — extraction happens once per job, matching runs entirely in the database.

**Core principle:** matching is the product. Extraction exists to feed it.

---

## How It Works

```mermaid
flowchart TD
    A[Postings JSONL] --> B[(job_postings)]
    B --> C[LLM Extraction]
    C --> D[(job_profiles\naxes_vec · job_profile_skills)]

    E[PDF Resume] --> F[LLM Extraction]
    F --> G[(user_profiles\naxes_vec · resume_skills)]

    D --> H[Stage 1 — pgvector L2 similarity]
    G --> H
    H --> I[Stage 2 — Skill overlap SQL]
    I --> J[Stage 3 — LLM rerank · optional]
    J --> K[(match_results)]
```

### Three-stage matching pipeline

| Stage | Method | LLM? |
|-------|--------|-------|
| Stage 1 | pgvector L2 similarity on `axes_vec` + soft role/seniority boost | No |
| Stage 2 | SQL keyword overlap: `job_profile_skills ⋈ resume_skills`, scored by importance | No |
| Stage 3 | LLM rerank on top 10–20 using full `profile_json` | Yes (optional) |

Stage 1 is live. Stages 2 and 3 are in progress.

---

## Competency Axes

Every job profile and user profile is scored across 6 axes by the LLM at extraction time. These form a `vector(6)` used in stage 1 matching.

| Axis | What it measures |
|------|-----------------|
| `axis_backend` | APIs, services, databases, queues, caching, distributed systems |
| `axis_frontend` | React/Next.js, UI, browser performance, UX |
| `axis_platform` | Cloud infra, Kubernetes, containers, IaC, deployment |
| `axis_ai_data` | LLMs, ML systems, RAG, data pipelines, analytics |
| `axis_security_reliability` | Security, observability, on-call, incident response, testing |
| `axis_product_ownership` | Feature ownership, PM/design collab, experimentation, metrics |

Scores are floats from `0.0` to `1.0` and do not need to sum to 1. `axis_fullstack_span` is derived: `min(2 * min(backend, frontend), 1.0)`.

Scoring is guided by `docs/AXIS_MEASURE_SKILL.md` (axis definitions, signal weighting rules) and `docs/references/calibration_anchors.md` (hand-scored reference roles).

### Why L2, not cosine

Stage 1 uses L2 (Euclidean) distance via pgvector's `<->` operator. Cosine similarity measures direction only — a job requiring light backend (`0.3`) and a job requiring heavy backend (`0.9`) look identical to cosine if proportions match. L2 penalises both directional and magnitude differences, which better reflects whether a job's requirements actually align with a candidate's strength profile.

---

## Skills Pipeline

Each job profile and resume profile populates junction tables with canonicalized skill tags:

- `skills_catalog` — 235 canonical skills with category and source
- `skill_aliases` — 115 alias → canonical mappings (e.g. `k8s` → `Kubernetes`, `react.js` → `React`)
- `job_profile_skills` — one row per skill × importance (`must`, `preferred`, `nice`) per active job profile
- `resume_skills` — one row per skill per active user profile

Skills are canonicalized at write time via `src/skills.py`. Unknown skills auto-insert with `source='auto'`.

---

## CLI

All pipeline operations run through `src/cli.py`. No FastAPI yet — the API layer is a planned next step.

```bash
# Apply schema migrations
python src/cli.py migrate

# Ingest + extract job postings from a LinkedIn JSONL export
python src/cli.py run

# Extract a structured profile from a PDF resume
python src/cli.py ingest-resume path/to/resume.pdf --email user@example.com

# Find top 5 matching jobs for a user (read-only, no ingestion)
python src/cli.py match --email user@example.com

# Same with a pgvector vs naive Python timing comparison
python src/cli.py match --email user@example.com --benchmark
```

The `match` command prompts interactively for preferred role family and seniority (soft boosts, not hard filters), then returns the top 5 jobs ranked by L2 axis similarity.

---

## Schema

Eight tables, applied alphabetically from `scripts/migrations/`:

```
job_postings          one row per posting; content_hash + profile_status
    ↓ 1:N
job_profiles          semantic cache; profile_json + ~30 denormalized columns + axes_vec vector(6)
    ↓ 1:N
job_profile_skills    inverted index; one row per skill × importance per active profile

users                 one row per user; email unique
    ↓ 1:N
user_profiles         resume extraction cache; same versioning pattern as job_profiles
    ↓ 1:N
resume_skills         one row per skill per active resume

skills_catalog        canonical skills vocabulary
skill_aliases         alias → skill_id lookup
```

Versioning tuple: `(content_hash, schema_version, prompt_version, model_version)`. Re-extraction is triggered when any element of the tuple changes. The previous profile row is superseded (`is_active = 0`), not deleted.

---

## Project Structure

```
src/
  cli.py                    CLI entry point — routing and I/O only
  db.py                     All CRUD + schema migrations
  skills.py                 canonicalize() and batch_canonicalize()
  profile_columns.py        JobProfile → job_profiles column builder
  user_profile_columns.py   UserProfile → user_profiles column builder
  models/
    job_profile.py          JobProfile, ExtractionResult, Axes, Skills
    user_profile.py         UserProfile, ResumeExtractionResult, ResumeSkills
  pipeline/
    ingest.py               LinkedIn JSONL → job_postings
    extract.py              job_postings → job_profiles (LLM)
    extract_resume.py       PDF → user_profiles (LLM)
    match1.py               Stage 1: L2 similarity via pgvector + naive benchmark path
    match2.py               Stage 2: keyword overlap (in progress)
  prompts/
    extraction.txt          Job extraction prompt (versioned)
    extraction_resume.txt   Resume extraction prompt (versioned)

scripts/migrations/
  005_postgres_baseline.sql
  006_skills_catalog.sql
  007_add_axes_vec.sql
  008_swap_hnsw_to_l2.sql

tests/                      69 tests; all DB tests use temp_db fixture
docs/
  CONTEXT.md                Architectural rationale and query shapes
  TODO_LIST.md              PR sequence
  AXIS_MEASURE_SKILL.md     Axis scoring rubric embedded in extraction prompt
  references/
    calibration_anchors.md  Hand-scored reference roles for axis calibration
```

---

## Setup

**Prerequisites:** Python 3.12, PostgreSQL with the `pgvector` extension, an OpenAI API key.

```bash
git clone https://github.com/ibrahimk2002/job-match-agent.git
cd job-match-agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```
OPENAI_API_KEY=your_openai_key
DATABASE_URL=postgresql://user:password@localhost:5432/job_match_agent
```

Apply migrations and run:

```bash
python src/cli.py migrate
python src/cli.py run
```

---

## Testing

```bash
pytest tests/ -v
```

69 tests. All database tests use the `temp_db` fixture which monkeypatches to a fresh test database and tears down after each test. No test references a real database path.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| Database | PostgreSQL + pgvector |
| LLM | OpenAI GPT-4.1 Nano |
| Validation | Pydantic v2 |
| PDF parsing | pypdf |
| Testing | pytest |

---

## License

Proprietary. All rights reserved. Unauthorized copying, distribution, modification, or commercial use is not permitted without explicit permission.
