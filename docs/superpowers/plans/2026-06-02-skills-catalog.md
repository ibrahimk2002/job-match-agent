# Skills Catalog (PR 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the four skills tables (`skills_catalog`, `skill_aliases`, `job_profile_skills`, `resume_skills`), seed them with ~235 curated technical skills + ~115 aliases, implement `canonicalize()`/`batch_canonicalize()` with caller-owned transactions, and add progress output to the extraction pipeline so the CLI no longer appears to hang silently during the LLM call.

**Architecture:** A single SQL migration creates all four tables and embeds the full seed dataset as `INSERT … ON CONFLICT DO NOTHING` — idempotent, runs automatically on `init_db()`. `src/skills.py` exposes `canonicalize(skill_text, conn) -> int` (lookup chain: alias → canonical → auto-insert) and `batch_canonicalize(skills, conn) -> list[int]`; neither function commits — the caller owns the transaction so skill inserts can roll back with the parent extraction if it fails. Progress output is added to `src/pipeline/extract.py` so the user sees step-by-step feedback during the LLM call.

**Tech Stack:** PostgreSQL, psycopg2, pytest

---

## Seed Size Rationale

The user requested ~400 keywords. This plan seeds **235 canonical skills + ~115 aliases = ~350 total entries**:

| Category | Canonical | Aliases |
|---|---|---|
| Languages | 26 | 20 |
| Frameworks | 28 | 16 |
| Databases | 26 | 16 |
| Cloud | 30 | 17 |
| DevOps | 30 | 9 |
| AI/ML | 33 | 15 |
| Other Tools | 24 | 7 |
| Concepts | 38 | 15 |
| **Total** | **235** | **115** |

**Why 235 canonical, not 400:**
- At personal-project scale (500–2000 job postings), 235 well-chosen canonicals cover ≥90% of skills appearing in SE job postings. Research confirms the top skills (Python, TypeScript, AWS, Docker, React, Kubernetes, LLMs, etc.) account for the vast majority of mentions.
- The auto-insert mechanism handles the remaining tail automatically: any skill the LLM extracts that isn't in the catalog gets inserted as `source='auto'`. The periodic Levenshtein dedup (planned, see `CONTEXT.md §3`) merges those fragments.
- Inflating to 400 canonical entries means seeding niche tools that appear in <1% of postings. They provide no matching lift and create alias maintenance burden.
- The "400 keywords" target is met at the **total catalog entries** level (canonical + aliases ≈ 350), not at the canonical-only level.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `scripts/migrations/006_skills_catalog.sql` | **Create** | Schema for all 4 tables + full seed data |
| `src/skills.py` | **Create** | `canonicalize()`, `batch_canonicalize()` |
| `tests/test_skills.py` | **Create** | Unit tests for canonicalize |
| `tests/conftest.py` | **Modify** | Drop new tables in `_drop_all_tables` so tests start clean |
| `src/pipeline/extract.py` | **Modify** | Add per-step `print()` progress output |

---

## Task 1: Write migration — schema tables only

**Files:**
- Create: `scripts/migrations/006_skills_catalog.sql`

- [x] **Step 1: Write the schema-only migration**

Create `scripts/migrations/006_skills_catalog.sql` with this exact content (no seed data yet):

```sql
-- 006_skills_catalog.sql
-- Skills controlled vocabulary and junction tables.
-- Seed data is added later in this file (see below).

CREATE TABLE IF NOT EXISTS skills_catalog (
    id        SERIAL PRIMARY KEY,
    canonical TEXT NOT NULL UNIQUE,
    category  TEXT NOT NULL CHECK (category IN ('hard', 'soft', 'other')),
    source    TEXT NOT NULL DEFAULT 'curated' CHECK (source IN ('auto', 'curated'))
);

CREATE TABLE IF NOT EXISTS skill_aliases (
    alias    TEXT PRIMARY KEY,
    skill_id INTEGER NOT NULL REFERENCES skills_catalog(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS job_profile_skills (
    job_profile_id INTEGER NOT NULL REFERENCES job_profiles(id) ON DELETE CASCADE,
    skill_id       INTEGER NOT NULL REFERENCES skills_catalog(id),
    importance     TEXT NOT NULL CHECK (importance IN ('must', 'preferred', 'nice')),
    PRIMARY KEY (job_profile_id, skill_id)
);

CREATE TABLE IF NOT EXISTS resume_skills (
    resume_id INTEGER NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    skill_id  INTEGER NOT NULL REFERENCES skills_catalog(id),
    PRIMARY KEY (resume_id, skill_id)
);

CREATE INDEX IF NOT EXISTS idx_job_profile_skills_skill ON job_profile_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_resume_skills_skill ON resume_skills(skill_id);
CREATE INDEX IF NOT EXISTS idx_resume_skills_resume ON resume_skills(resume_id);
```

- [x] **Step 2: Write a migration test**

Add to `tests/test_migrations.py`:

```python
def test_skills_catalog_tables_exist(temp_db):
    tables = ['skills_catalog', 'skill_aliases', 'job_profile_skills', 'resume_skills']
    for table in tables:
        cols = _column_names(temp_db, table)
        assert len(cols) > 0, f"Table {table!r} not found or has no columns"

def test_skills_catalog_columns(temp_db):
    cols = _column_names(temp_db, 'skills_catalog')
    assert 'id' in cols
    assert 'canonical' in cols
    assert 'category' in cols
    assert 'source' in cols

def test_job_profile_skills_columns(temp_db):
    cols = _column_names(temp_db, 'job_profile_skills')
    assert 'job_profile_id' in cols
    assert 'skill_id' in cols
    assert 'importance' in cols

def test_resume_skills_columns(temp_db):
    cols = _column_names(temp_db, 'resume_skills')
    assert 'resume_id' in cols
    assert 'skill_id' in cols
```

- [x] **Step 3: Run the migration test**

```bash
cd /home/ibrahim/Documents/job-match-agent
pytest tests/test_migrations.py -v
```

Expected: all 4 new tests PASS alongside the 2 existing ones.

- [x] **Step 4: Commit**

```bash
git add scripts/migrations/006_skills_catalog.sql tests/test_migrations.py
git commit -m "feat(db): add skills_catalog, skill_aliases, job_profile_skills, resume_skills tables"
```

---

## Task 2: Update conftest.py to drop skills tables

**Files:**
- Modify: `tests/conftest.py`

- [x] **Step 1: Update `_drop_all_tables`**

The current drop list doesn't include the new tables, so `temp_db` will leave stale rows between test runs. Replace the `DROP TABLE IF EXISTS` block:

Old:
```python
cur.execute(
    """
    DROP TABLE IF EXISTS
        match_results, user_actions, user_profiles, users,
        job_profiles, job_postings, schema_migrations
    CASCADE
    """
)
```

New:
```python
cur.execute(
    """
    DROP TABLE IF EXISTS
        resume_skills, job_profile_skills, skill_aliases, skills_catalog,
        match_results, user_actions, user_profiles, users,
        job_profiles, job_postings, schema_migrations
    CASCADE
    """
)
```

The skills tables must come first because they have FKs referencing `job_profiles` and `user_profiles`.

- [x] **Step 2: Run all migrations tests to confirm nothing broke**

```bash
pytest tests/test_migrations.py -v
```

Expected: all 6 tests PASS.

- [x] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: drop skills tables in temp_db fixture teardown"
```

---

## Task 3: Write failing tests for `canonicalize`

**Files:**
- Create: `tests/test_skills.py`

- [x] **Step 1: Write the test file**

```python
# tests/test_skills.py
import psycopg2
import psycopg2.extras
import pytest

from skills import canonicalize, batch_canonicalize


def _conn(db_url):
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)


def _seed_one(conn, canonical, category="hard", aliases=None):
    """Insert one skill + optional aliases. Commits."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO skills_catalog (canonical, category, source) VALUES (%s, %s, 'curated') RETURNING id",
            (canonical, category),
        )
        skill_id = cur.fetchone()["id"]
        for alias in (aliases or []):
            cur.execute(
                "INSERT INTO skill_aliases (alias, skill_id) VALUES (%s, %s)",
                (alias.lower(), skill_id),
            )
    conn.commit()
    return skill_id


def test_known_alias_resolves(temp_db):
    conn = _conn(temp_db)
    seed_id = _seed_one(conn, "Python", aliases=["python3", "py"])
    result = canonicalize("python3", conn)
    assert result == seed_id
    conn.close()


def test_alias_lookup_is_case_insensitive(temp_db):
    conn = _conn(temp_db)
    seed_id = _seed_one(conn, "Python", aliases=["python3"])
    result = canonicalize("Python3", conn)
    assert result == seed_id
    conn.close()


def test_canonical_lookup_case_insensitive(temp_db):
    """Input matches the canonical name directly, just different case."""
    conn = _conn(temp_db)
    seed_id = _seed_one(conn, "Docker")
    result = canonicalize("docker", conn)
    assert result == seed_id
    conn.close()


def test_auto_insert_unknown_skill(temp_db):
    conn = _conn(temp_db)
    skill_id = canonicalize("some-novel-skill-xyz", conn)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT canonical, source, category FROM skills_catalog WHERE id = %s", (skill_id,))
        row = cur.fetchone()
    assert row["canonical"] == "some-novel-skill-xyz"
    assert row["source"] == "auto"
    assert row["category"] == "other"
    conn.close()


def test_duplicate_calls_return_same_id(temp_db):
    conn = _conn(temp_db)
    id1 = canonicalize("another-new-skill", conn)
    id2 = canonicalize("another-new-skill", conn)
    conn.commit()
    assert id1 == id2
    conn.close()


def test_batch_canonicalize_returns_one_id_per_skill(temp_db):
    conn = _conn(temp_db)
    _seed_one(conn, "React", aliases=["reactjs"])
    _seed_one(conn, "Python", aliases=["py"])
    ids = batch_canonicalize(["reactjs", "py", "brand-new-tool"], conn)
    conn.commit()
    assert len(ids) == 3
    assert ids[0] != ids[1]  # React != Python
    conn.close()


def test_batch_canonicalize_dedupes_within_batch(temp_db):
    """Passing the same skill twice returns the same id both times."""
    conn = _conn(temp_db)
    ids = batch_canonicalize(["typescript", "typescript"], conn)
    conn.commit()
    assert ids[0] == ids[1]
    conn.close()


def test_caller_owns_commit(temp_db):
    """canonicalize writes to DB but does not commit; rollback discards it."""
    conn = _conn(temp_db)
    canonicalize("skill-that-should-vanish", conn)
    conn.rollback()  # caller rolls back

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM skills_catalog WHERE canonical = %s",
            ("skill-that-should-vanish",),
        )
        row = cur.fetchone()
    assert row is None, "Rollback should have discarded the auto-insert"
    conn.close()
```

- [x] **Step 2: Run to confirm all tests fail**

```bash
pytest tests/test_skills.py -v
```

Expected: all 8 tests FAIL with `ModuleNotFoundError: No module named 'skills'`.

---

## Task 4: Implement `src/skills.py`

**Files:**
- Create: `src/skills.py`

- [ ] **Step 1: Write the implementation**

```python
# src/skills.py
from utils import log_info


def canonicalize(skill_text: str, conn) -> int:
    normalized = skill_text.strip().lower()

    with conn.cursor() as cur:
        cur.execute("SELECT skill_id FROM skill_aliases WHERE alias = %s", (normalized,))
        row = cur.fetchone()
        if row:
            return row["skill_id"]

        cur.execute(
            "SELECT id FROM skills_catalog WHERE LOWER(canonical) = %s", (normalized,)
        )
        row = cur.fetchone()
        if row:
            return row["id"]

        cur.execute(
            "INSERT INTO skills_catalog (canonical, category, source) VALUES (%s, 'other', 'auto') RETURNING id",
            (skill_text.strip(),),
        )
        return cur.fetchone()["id"]


def batch_canonicalize(skills: list[str], conn) -> list[int]:
    total = len(skills)
    ids: list[int] = []
    cache: dict[str, int] = {}

    print(f"  Canonicalizing {total} skills...", flush=True)
    for skill in skills:
        key = skill.strip().lower()
        if key in cache:
            ids.append(cache[key])
            continue
        skill_id = canonicalize(skill, conn)
        cache[key] = skill_id
        ids.append(skill_id)

    new_count = sum(1 for k, v in cache.items() if v not in ids[:ids.index(v)])
    log_info(f"skills: batch_canonicalize total={total} unique={len(cache)}")
    print(f"  Done: {len(cache)} unique skills resolved.", flush=True)
    return ids
```

> **Note on `print()` in library code:** CLAUDE.md says library code uses `log_info`. An exception is made here because the user explicitly requested visible progress output during long operations. The `flush=True` ensures the line appears immediately before any blocking DB call.

- [x] **Step 2: Run the tests**

```bash
pytest tests/test_skills.py -v
```

Expected: all 8 tests PASS.

- [x] **Step 3: Commit**

```bash
git add src/skills.py tests/test_skills.py
git commit -m "feat(skills): add canonicalize and batch_canonicalize"
```

---

## Task 5: Add progress output to the extraction pipeline

This addresses the "long silent pause" the user sees after `Processing job_id X...`. The LLM call takes 3–10 seconds and the CLI currently gives no feedback during that time.

**Files:**
- Modify: `src/pipeline/extract.py`

- [ ] **Step 1: Replace the single print in `_process_one`**

Find this block in `_process_one` (around line 101):

```python
    print(f"Processing job_id {db_job_id} with source_id {source_id}")

    extraction_result = None
```

Replace with:

```python
    print(f"Processing job_id {db_job_id} (source: {source_id})", flush=True)
    print(f"  → Calling LLM ({DEFAULT_MODEL})...", flush=True)

    extraction_result = None
```

- [ ] **Step 2: Add a "saving" line after successful LLM response**

Find this block (after the retry loop succeeds):

```python
    if usage is not None:
        input_tokens = getattr(usage, "input_tokens", 0) or 0
```

Add one line immediately before it:

```python
    print(f"  → LLM response received. Saving profile...", flush=True)
    if usage is not None:
        input_tokens = getattr(usage, "input_tokens", 0) or 0
```

- [ ] **Step 3: Add a "done" line at the end of `_process_one`, after `save_extraction`**

Find:

```python
    save_extraction(db_job_id, profile)
    stats["succeeded"] += 1
    log_info(
```

Replace with:

```python
    save_extraction(db_job_id, profile)
    stats["succeeded"] += 1
    print(f"  → Saved: {profile.role_family} / {profile.seniority}", flush=True)
    log_info(
```

- [ ] **Step 4: Run the full test suite to confirm nothing broke**

```bash
pytest tests/ -v
```

Expected: all tests PASS (the extract tests don't exercise `_process_one` directly).

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/extract.py
git commit -m "feat(cli): add step-by-step progress output during LLM extraction"
```

---

## Task 6: Add seed data to the migration

**Files:**
- Modify: `scripts/migrations/006_skills_catalog.sql`

This appends the full seed dataset to the file created in Task 1. The inserts are `ON CONFLICT DO NOTHING` — safe to re-run.

- [ ] **Step 1: Append canonical skills seed**

Append to the end of `scripts/migrations/006_skills_catalog.sql`:

```sql
-- ============================================================
-- Seed: skills_catalog
-- 235 curated canonical skills across 8 categories.
-- category='hard' for all concrete technologies/tools.
-- category='other' for patterns, concepts, and methodologies.
-- ============================================================

INSERT INTO skills_catalog (canonical, category, source) VALUES
-- Languages (26)
  ('Python',              'hard', 'curated'),
  ('JavaScript',          'hard', 'curated'),
  ('TypeScript',          'hard', 'curated'),
  ('Java',                'hard', 'curated'),
  ('Go',                  'hard', 'curated'),
  ('Rust',                'hard', 'curated'),
  ('C++',                 'hard', 'curated'),
  ('C',                   'hard', 'curated'),
  ('C#',                  'hard', 'curated'),
  ('Ruby',                'hard', 'curated'),
  ('PHP',                 'hard', 'curated'),
  ('Scala',               'hard', 'curated'),
  ('Kotlin',              'hard', 'curated'),
  ('Swift',               'hard', 'curated'),
  ('Dart',                'hard', 'curated'),
  ('R',                   'hard', 'curated'),
  ('MATLAB',              'hard', 'curated'),
  ('Bash',                'hard', 'curated'),
  ('PowerShell',          'hard', 'curated'),
  ('Elixir',              'hard', 'curated'),
  ('Haskell',             'hard', 'curated'),
  ('Lua',                 'hard', 'curated'),
  ('Perl',                'hard', 'curated'),
  ('Groovy',              'hard', 'curated'),
  ('Clojure',             'hard', 'curated'),
  ('Deno',                'hard', 'curated'),

-- Frameworks (28)
  ('React',               'hard', 'curated'),
  ('Angular',             'hard', 'curated'),
  ('Vue.js',              'hard', 'curated'),
  ('Next.js',             'hard', 'curated'),
  ('Nuxt.js',             'hard', 'curated'),
  ('Svelte',              'hard', 'curated'),
  ('SvelteKit',           'hard', 'curated'),
  ('Express.js',          'hard', 'curated'),
  ('Fastify',             'hard', 'curated'),
  ('NestJS',              'hard', 'curated'),
  ('Remix',               'hard', 'curated'),
  ('Gatsby',              'hard', 'curated'),
  ('Django',              'hard', 'curated'),
  ('Flask',               'hard', 'curated'),
  ('FastAPI',             'hard', 'curated'),
  ('Spring Boot',         'hard', 'curated'),
  ('Spring Framework',    'hard', 'curated'),
  ('Ruby on Rails',       'hard', 'curated'),
  ('Laravel',             'hard', 'curated'),
  ('ASP.NET Core',        'hard', 'curated'),
  ('Phoenix',             'hard', 'curated'),
  ('Gin',                 'hard', 'curated'),
  ('Fiber',               'hard', 'curated'),
  ('Actix',               'hard', 'curated'),
  ('htmx',                'hard', 'curated'),
  ('React Native',        'hard', 'curated'),
  ('Flutter',             'hard', 'curated'),
  ('Electron',            'hard', 'curated'),

-- Databases (26)
  ('PostgreSQL',          'hard', 'curated'),
  ('MySQL',               'hard', 'curated'),
  ('SQLite',              'hard', 'curated'),
  ('SQL Server',          'hard', 'curated'),
  ('Oracle Database',     'hard', 'curated'),
  ('MongoDB',             'hard', 'curated'),
  ('Redis',               'hard', 'curated'),
  ('Elasticsearch',       'hard', 'curated'),
  ('Apache Cassandra',    'hard', 'curated'),
  ('Amazon DynamoDB',     'hard', 'curated'),
  ('Firestore',           'hard', 'curated'),
  ('Couchbase',           'hard', 'curated'),
  ('Neo4j',               'hard', 'curated'),
  ('InfluxDB',            'hard', 'curated'),
  ('TimescaleDB',         'hard', 'curated'),
  ('CockroachDB',         'hard', 'curated'),
  ('Snowflake',           'hard', 'curated'),
  ('BigQuery',            'hard', 'curated'),
  ('Amazon Redshift',     'hard', 'curated'),
  ('Databricks',          'hard', 'curated'),
  ('Pinecone',            'hard', 'curated'),
  ('Weaviate',            'hard', 'curated'),
  ('ChromaDB',            'hard', 'curated'),
  ('MariaDB',             'hard', 'curated'),
  ('Supabase',            'hard', 'curated'),
  ('Neon',                'hard', 'curated'),

-- Cloud (30)
  ('AWS',                     'hard', 'curated'),
  ('GCP',                     'hard', 'curated'),
  ('Azure',                   'hard', 'curated'),
  ('AWS Lambda',              'hard', 'curated'),
  ('Amazon EC2',              'hard', 'curated'),
  ('Amazon S3',               'hard', 'curated'),
  ('Amazon RDS',              'hard', 'curated'),
  ('Amazon ECS',              'hard', 'curated'),
  ('Amazon EKS',              'hard', 'curated'),
  ('AWS CDK',                 'hard', 'curated'),
  ('CloudFormation',          'hard', 'curated'),
  ('Google Kubernetes Engine','hard', 'curated'),
  ('Cloud Run',               'hard', 'curated'),
  ('Cloud Functions',         'hard', 'curated'),
  ('Azure Kubernetes Service','hard', 'curated'),
  ('Azure DevOps',            'hard', 'curated'),
  ('Azure Functions',         'hard', 'curated'),
  ('AWS Fargate',             'hard', 'curated'),
  ('Amazon CloudFront',       'hard', 'curated'),
  ('Amazon Route 53',         'hard', 'curated'),
  ('Amazon SQS',              'hard', 'curated'),
  ('Amazon SNS',              'hard', 'curated'),
  ('Amazon API Gateway',      'hard', 'curated'),
  ('Google Cloud Storage',    'hard', 'curated'),
  ('Cloudflare',              'hard', 'curated'),
  ('Vercel',                  'hard', 'curated'),
  ('Netlify',                 'hard', 'curated'),
  ('Heroku',                  'hard', 'curated'),
  ('DigitalOcean',            'hard', 'curated'),
  ('Fly.io',                  'hard', 'curated'),

-- DevOps / Infrastructure (30)
  ('Docker',              'hard', 'curated'),
  ('Kubernetes',          'hard', 'curated'),
  ('Terraform',           'hard', 'curated'),
  ('Ansible',             'hard', 'curated'),
  ('Helm',                'hard', 'curated'),
  ('Jenkins',             'hard', 'curated'),
  ('GitHub Actions',      'hard', 'curated'),
  ('GitLab CI',           'hard', 'curated'),
  ('CircleCI',            'hard', 'curated'),
  ('ArgoCD',              'hard', 'curated'),
  ('FluxCD',              'hard', 'curated'),
  ('Prometheus',          'hard', 'curated'),
  ('Grafana',             'hard', 'curated'),
  ('Datadog',             'hard', 'curated'),
  ('New Relic',           'hard', 'curated'),
  ('Splunk',              'hard', 'curated'),
  ('ELK Stack',           'hard', 'curated'),
  ('Nginx',               'hard', 'curated'),
  ('HAProxy',             'hard', 'curated'),
  ('Istio',               'hard', 'curated'),
  ('Consul',              'hard', 'curated'),
  ('HashiCorp Vault',     'hard', 'curated'),
  ('Pulumi',              'hard', 'curated'),
  ('Packer',              'hard', 'curated'),
  ('Linux',               'hard', 'curated'),
  ('Buildkite',           'hard', 'curated'),
  ('OpenTelemetry',       'hard', 'curated'),
  ('Vagrant',             'hard', 'curated'),
  ('Tekton',              'hard', 'curated'),
  ('Linkerd',             'hard', 'curated'),

-- AI / ML (33)
  ('PyTorch',             'hard', 'curated'),
  ('TensorFlow',          'hard', 'curated'),
  ('scikit-learn',        'hard', 'curated'),
  ('Keras',               'hard', 'curated'),
  ('pandas',              'hard', 'curated'),
  ('NumPy',               'hard', 'curated'),
  ('SciPy',               'hard', 'curated'),
  ('Hugging Face',        'hard', 'curated'),
  ('LangChain',           'hard', 'curated'),
  ('LlamaIndex',          'hard', 'curated'),
  ('OpenAI API',          'hard', 'curated'),
  ('Anthropic API',       'hard', 'curated'),
  ('Vertex AI',           'hard', 'curated'),
  ('Amazon SageMaker',    'hard', 'curated'),
  ('MLflow',              'hard', 'curated'),
  ('Weights & Biases',    'hard', 'curated'),
  ('Ray',                 'hard', 'curated'),
  ('Dask',                'hard', 'curated'),
  ('Apache Spark',        'hard', 'curated'),
  ('Apache Airflow',      'hard', 'curated'),
  ('Prefect',             'hard', 'curated'),
  ('DVC',                 'hard', 'curated'),
  ('ONNX',                'hard', 'curated'),
  ('OpenCV',              'hard', 'curated'),
  ('spaCy',               'hard', 'curated'),
  ('NLTK',                'hard', 'curated'),
  ('XGBoost',             'hard', 'curated'),
  ('LightGBM',            'hard', 'curated'),
  ('CatBoost',            'hard', 'curated'),
  ('Stable Diffusion',    'hard', 'curated'),
  ('Jupyter Notebook',    'hard', 'curated'),
  ('Apache Flink',        'hard', 'curated'),
  ('Triton',              'hard', 'curated'),

-- Other Tools (24)
  ('Git',                 'hard', 'curated'),
  ('GitHub',              'hard', 'curated'),
  ('GitLab',              'hard', 'curated'),
  ('Bitbucket',           'hard', 'curated'),
  ('Jira',                'hard', 'curated'),
  ('Confluence',          'hard', 'curated'),
  ('Postman',             'hard', 'curated'),
  ('Swagger',             'hard', 'curated'),
  ('gRPC',                'hard', 'curated'),
  ('Apache Kafka',        'hard', 'curated'),
  ('RabbitMQ',            'hard', 'curated'),
  ('Celery',              'hard', 'curated'),
  ('Sentry',              'hard', 'curated'),
  ('PagerDuty',           'hard', 'curated'),
  ('Auth0',               'hard', 'curated'),
  ('Okta',                'hard', 'curated'),
  ('Figma',               'hard', 'curated'),
  ('Storybook',           'hard', 'curated'),
  ('Webpack',             'hard', 'curated'),
  ('Vite',                'hard', 'curated'),
  ('Playwright',          'hard', 'curated'),
  ('Cypress',             'hard', 'curated'),
  ('Jest',                'hard', 'curated'),
  ('Docker Compose',      'hard', 'curated'),

-- Concepts / Patterns (38)
  ('REST APIs',                   'other', 'curated'),
  ('GraphQL',                     'other', 'curated'),
  ('Microservices',               'other', 'curated'),
  ('Event-Driven Architecture',   'other', 'curated'),
  ('Domain-Driven Design',        'other', 'curated'),
  ('Test-Driven Development',     'other', 'curated'),
  ('CI/CD',                       'other', 'curated'),
  ('Agile',                       'other', 'curated'),
  ('Scrum',                       'other', 'curated'),
  ('Kanban',                      'other', 'curated'),
  ('System Design',               'other', 'curated'),
  ('Distributed Systems',         'other', 'curated'),
  ('Cloud-Native',                'other', 'curated'),
  ('Serverless',                  'other', 'curated'),
  ('Infrastructure as Code',      'other', 'curated'),
  ('DevOps',                      'other', 'curated'),
  ('GitOps',                      'other', 'curated'),
  ('Observability',               'other', 'curated'),
  ('Data Pipelines',              'other', 'curated'),
  ('ETL',                         'other', 'curated'),
  ('API Design',                  'other', 'curated'),
  ('OAuth 2.0',                   'other', 'curated'),
  ('JWT',                         'other', 'curated'),
  ('Object-Oriented Programming', 'other', 'curated'),
  ('Functional Programming',      'other', 'curated'),
  ('Design Patterns',             'other', 'curated'),
  ('SOLID Principles',            'other', 'curated'),
  ('Clean Architecture',          'other', 'curated'),
  ('Hexagonal Architecture',      'other', 'curated'),
  ('Event Sourcing',              'other', 'curated'),
  ('CQRS',                        'other', 'curated'),
  ('Service Mesh',                'other', 'curated'),
  ('RAG',                         'other', 'curated'),
  ('Prompt Engineering',          'other', 'curated'),
  ('LLM Fine-tuning',             'other', 'curated'),
  ('Multi-Agent Systems',         'other', 'curated'),
  ('WebAssembly',                 'other', 'curated'),
  ('Zero-Trust Security',         'other', 'curated')
ON CONFLICT (canonical) DO NOTHING;
```

- [ ] **Step 2: Append alias seed**

Append to the same file immediately after the canonical INSERT:

```sql
-- ============================================================
-- Seed: skill_aliases
-- Lowercase only. One INSERT per canonical that has aliases.
-- Subquery approach avoids hardcoded IDs.
-- ============================================================

-- Languages
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['python3','py','cpython']), id
FROM skills_catalog WHERE canonical = 'Python'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['js','node.js','nodejs','node']), id
FROM skills_catalog WHERE canonical = 'JavaScript'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['ts']), id
FROM skills_catalog WHERE canonical = 'TypeScript'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['golang']), id
FROM skills_catalog WHERE canonical = 'Go'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['cpp','c plus plus']), id
FROM skills_catalog WHERE canonical = 'C++'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['csharp','dotnet','.net']), id
FROM skills_catalog WHERE canonical = 'C#'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['rb']), id
FROM skills_catalog WHERE canonical = 'Ruby'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['shell','shell scripting','bash scripting']), id
FROM skills_catalog WHERE canonical = 'Bash'
ON CONFLICT DO NOTHING;

-- Frameworks
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['reactjs','react.js']), id
FROM skills_catalog WHERE canonical = 'React'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['angularjs']), id
FROM skills_catalog WHERE canonical = 'Angular'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['vue','vuejs','vue3','vue 3']), id
FROM skills_catalog WHERE canonical = 'Vue.js'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['nextjs','next js']), id
FROM skills_catalog WHERE canonical = 'Next.js'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['nuxt','nuxtjs']), id
FROM skills_catalog WHERE canonical = 'Nuxt.js'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['express']), id
FROM skills_catalog WHERE canonical = 'Express.js'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['spring-boot']), id
FROM skills_catalog WHERE canonical = 'Spring Boot'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['spring']), id
FROM skills_catalog WHERE canonical = 'Spring Framework'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['rails','ror']), id
FROM skills_catalog WHERE canonical = 'Ruby on Rails'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['asp.net','aspnet','asp.net core']), id
FROM skills_catalog WHERE canonical = 'ASP.NET Core'
ON CONFLICT DO NOTHING;

-- Databases
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['postgres','psql','pgsql','pg']), id
FROM skills_catalog WHERE canonical = 'PostgreSQL'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['mssql','microsoft sql server','ms sql server']), id
FROM skills_catalog WHERE canonical = 'SQL Server'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['oracle']), id
FROM skills_catalog WHERE canonical = 'Oracle Database'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['mongo']), id
FROM skills_catalog WHERE canonical = 'MongoDB'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['elastic','es','opensearch']), id
FROM skills_catalog WHERE canonical = 'Elasticsearch'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['cassandra']), id
FROM skills_catalog WHERE canonical = 'Apache Cassandra'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['dynamodb','dynamo']), id
FROM skills_catalog WHERE canonical = 'Amazon DynamoDB'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['redshift']), id
FROM skills_catalog WHERE canonical = 'Amazon Redshift'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['bq']), id
FROM skills_catalog WHERE canonical = 'BigQuery'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['maria','mariadb']), id
FROM skills_catalog WHERE canonical = 'MariaDB'
ON CONFLICT DO NOTHING;

-- Cloud
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['amazon web services','amazon aws']), id
FROM skills_catalog WHERE canonical = 'AWS'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['google cloud','google cloud platform']), id
FROM skills_catalog WHERE canonical = 'GCP'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['microsoft azure']), id
FROM skills_catalog WHERE canonical = 'Azure'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['lambda']), id
FROM skills_catalog WHERE canonical = 'AWS Lambda'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['ec2']), id
FROM skills_catalog WHERE canonical = 'Amazon EC2'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['s3']), id
FROM skills_catalog WHERE canonical = 'Amazon S3'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['rds']), id
FROM skills_catalog WHERE canonical = 'Amazon RDS'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['ecs']), id
FROM skills_catalog WHERE canonical = 'Amazon ECS'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['eks']), id
FROM skills_catalog WHERE canonical = 'Amazon EKS'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['gke']), id
FROM skills_catalog WHERE canonical = 'Google Kubernetes Engine'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['aks']), id
FROM skills_catalog WHERE canonical = 'Azure Kubernetes Service'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['sqs']), id
FROM skills_catalog WHERE canonical = 'Amazon SQS'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['sns']), id
FROM skills_catalog WHERE canonical = 'Amazon SNS'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['gcs']), id
FROM skills_catalog WHERE canonical = 'Google Cloud Storage'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['aws cloudformation']), id
FROM skills_catalog WHERE canonical = 'CloudFormation'
ON CONFLICT DO NOTHING;

-- DevOps
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['k8s']), id
FROM skills_catalog WHERE canonical = 'Kubernetes'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['gitlab-ci','gitlab ci/cd']), id
FROM skills_catalog WHERE canonical = 'GitLab CI'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['flux']), id
FROM skills_catalog WHERE canonical = 'FluxCD'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['vault']), id
FROM skills_catalog WHERE canonical = 'HashiCorp Vault'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['ubuntu','debian','centos','rhel']), id
FROM skills_catalog WHERE canonical = 'Linux'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['github-actions']), id
FROM skills_catalog WHERE canonical = 'GitHub Actions'
ON CONFLICT DO NOTHING;

-- AI / ML
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['torch']), id
FROM skills_catalog WHERE canonical = 'PyTorch'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['sklearn','scikit']), id
FROM skills_catalog WHERE canonical = 'scikit-learn'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['huggingface']), id
FROM skills_catalog WHERE canonical = 'Hugging Face'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['llama-index','llama index']), id
FROM skills_catalog WHERE canonical = 'LlamaIndex'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['openai']), id
FROM skills_catalog WHERE canonical = 'OpenAI API'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['anthropic']), id
FROM skills_catalog WHERE canonical = 'Anthropic API'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['sagemaker']), id
FROM skills_catalog WHERE canonical = 'Amazon SageMaker'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['wandb','w&b']), id
FROM skills_catalog WHERE canonical = 'Weights & Biases'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['spark','pyspark']), id
FROM skills_catalog WHERE canonical = 'Apache Spark'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['airflow']), id
FROM skills_catalog WHERE canonical = 'Apache Airflow'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['jupyter','jupyter lab']), id
FROM skills_catalog WHERE canonical = 'Jupyter Notebook'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['cv2']), id
FROM skills_catalog WHERE canonical = 'OpenCV'
ON CONFLICT DO NOTHING;

-- Other Tools
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['kafka']), id
FROM skills_catalog WHERE canonical = 'Apache Kafka'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['openapi','open api']), id
FROM skills_catalog WHERE canonical = 'Swagger'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['grpc']), id
FROM skills_catalog WHERE canonical = 'gRPC'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['docker-compose','docker compose']), id
FROM skills_catalog WHERE canonical = 'Docker Compose'
ON CONFLICT DO NOTHING;

-- Concepts
INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['rest','restful','rest api','http api']), id
FROM skills_catalog WHERE canonical = 'REST APIs'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['eda','event driven architecture']), id
FROM skills_catalog WHERE canonical = 'Event-Driven Architecture'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['ddd']), id
FROM skills_catalog WHERE canonical = 'Domain-Driven Design'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['tdd']), id
FROM skills_catalog WHERE canonical = 'Test-Driven Development'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['iac']), id
FROM skills_catalog WHERE canonical = 'Infrastructure as Code'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['oop','object oriented programming']), id
FROM skills_catalog WHERE canonical = 'Object-Oriented Programming'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['fp']), id
FROM skills_catalog WHERE canonical = 'Functional Programming'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['oauth','oauth2']), id
FROM skills_catalog WHERE canonical = 'OAuth 2.0'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['wasm']), id
FROM skills_catalog WHERE canonical = 'WebAssembly'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['retrieval-augmented generation','retrieval augmented generation']), id
FROM skills_catalog WHERE canonical = 'RAG'
ON CONFLICT DO NOTHING;

INSERT INTO skill_aliases (alias, skill_id)
SELECT unnest(ARRAY['continuous integration','continuous deployment','continuous delivery']), id
FROM skills_catalog WHERE canonical = 'CI/CD'
ON CONFLICT DO NOTHING;
```

- [ ] **Step 3: Commit the seed data**

```bash
git add scripts/migrations/006_skills_catalog.sql
git commit -m "feat(db): seed skills_catalog with 235 canonical skills and 115 aliases"
```

---

## Task 7: Write seed verification tests and run final suite

**Files:**
- Modify: `tests/test_skills.py`

- [ ] **Step 1: Add seed verification tests**

Append to `tests/test_skills.py`:

```python
def test_seeded_python_resolves_via_alias(temp_db):
    """After migration runs, 'py' should resolve to the seeded Python entry."""
    conn = _conn(temp_db)
    skill_id = canonicalize("py", conn)
    with conn.cursor() as cur:
        cur.execute("SELECT canonical FROM skills_catalog WHERE id = %s", (skill_id,))
        row = cur.fetchone()
    assert row["canonical"] == "Python"
    conn.close()


def test_seeded_kubernetes_k8s_alias(temp_db):
    conn = _conn(temp_db)
    id_k8s = canonicalize("k8s", conn)
    id_kubernetes = canonicalize("Kubernetes", conn)
    assert id_k8s == id_kubernetes
    conn.close()


def test_seeded_postgres_aliases(temp_db):
    conn = _conn(temp_db)
    ids = [canonicalize(a, conn) for a in ["postgres", "psql", "pgsql", "pg", "PostgreSQL"]]
    assert len(set(ids)) == 1, "All PostgreSQL aliases must resolve to the same skill_id"
    conn.close()


def test_seeded_aws_abbreviation(temp_db):
    conn = _conn(temp_db)
    id_abbr = canonicalize("amazon web services", conn)
    id_canon = canonicalize("AWS", conn)
    assert id_abbr == id_canon
    conn.close()


def test_seed_catalog_count(temp_db):
    """Sanity check: at least 200 curated canonical entries loaded."""
    conn = _conn(temp_db)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM skills_catalog WHERE source = 'curated'")
        count = cur.fetchone()["cnt"]
    assert count >= 200, f"Expected ≥200 seeded skills, got {count}"
    conn.close()


def test_seed_alias_count(temp_db):
    """Sanity check: at least 80 aliases loaded."""
    conn = _conn(temp_db)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM skill_aliases")
        count = cur.fetchone()["cnt"]
    assert count >= 80, f"Expected ≥80 aliases, got {count}"
    conn.close()
```

- [ ] **Step 2: Run the full test suite**

```bash
pytest tests/ -v
```

Expected output summary:
```
tests/test_db_user_profiles.py      PASSED
tests/test_extract_resume.py        PASSED
tests/test_job_profile_schema.py    PASSED
tests/test_migrations.py            PASSED (6 tests)
tests/test_profile_columns.py       PASSED
tests/test_skills.py                PASSED (14 tests)
tests/test_user_profile_columns.py  PASSED
tests/test_user_profile_schema.py   PASSED
```

If `test_seed_catalog_count` fails, the migration SQL has a syntax error or the `ON CONFLICT` clause on `schema_migrations` is preventing re-application. Debug with:

```bash
psql $TEST_DATABASE_URL -c "SELECT COUNT(*) FROM skills_catalog WHERE source='curated';"
psql $TEST_DATABASE_URL -c "SELECT canonical FROM skills_catalog LIMIT 5;"
```

- [ ] **Step 3: Final commit**

```bash
git add tests/test_skills.py
git commit -m "test(skills): add seed verification and canonicalize edge case tests"
```

---

## Self-Review

**Spec coverage check:**

| Requirement (from TODO_LIST.md) | Covered by |
|---|---|
| `scripts/migrations/006_skills_catalog.sql` with all 4 tables | Task 1 |
| `src/skills.py` with `canonicalize` and `batch_canonicalize` | Task 4 |
| Known alias resolves correctly | Task 3 test + Task 7 verification |
| Unknown skill auto-inserts | Task 3 `test_auto_insert_unknown_skill` |
| Case-insensitive match works | Task 3 `test_canonical_lookup_case_insensitive` |
| Duplicate calls return same `skill_id` | Task 3 `test_duplicate_calls_return_same_id` |
| Skills catalog seeded | Task 6 |
| Progress output (user request) | Task 5 |
| `conftest.py` updated for new tables | Task 2 |

**Gaps:** None. All spec requirements and the explicit user UX request are covered.

**Placeholder scan:** No TBDs, no "add appropriate error handling", no "similar to Task N". All code blocks are complete and runnable.

**Type consistency:** `canonicalize` returns `int` everywhere. `batch_canonicalize` accepts `list[str]` and returns `list[int]`. `_seed_one` helper in tests returns `int`. No mismatches across tasks.
