# PR 2 — Postgres Migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Swap the database driver from SQLite to PostgreSQL — purely infrastructure, no logic changes, every subsequent PR builds on this.

**Architecture:** Replace `sqlite3` with `psycopg2` in `src/db.py`, read `DATABASE_URL` from the environment, swap `?` placeholders for `%s`, replace `executescript()` with cursor-based statement execution, and create a fresh Postgres-dialect baseline migration (`005`). Delete the four SQLite-specific migrations (001–004) — they're superseded by the Postgres baseline. Update `tests/conftest.py` to spin up against a test Postgres DB and patch `DATABASE_URL` via `monkeypatch.setenv`. Update three test files that call `sqlite3` directly.

**Tech Stack:** Python 3.11+, psycopg2-binary, pgvector (Postgres extension), pytest, PostgreSQL 14+

**Prerequisite — local Postgres setup:**
1. Install PostgreSQL (Ubuntu: `sudo apt-get install postgresql`)
2. Install pgvector extension (Ubuntu: `sudo apt-get install postgresql-16-pgvector` — match your PG version)
3. Create application and test databases:
   ```bash
   sudo -u postgres psql -c "CREATE DATABASE jobmatch;"
   sudo -u postgres psql -c "CREATE DATABASE jobmatch_test;"
   sudo -u postgres psql -c "CREATE USER jobmatch_user WITH PASSWORD 'changeme';"
   sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE jobmatch TO jobmatch_user;"
   sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE jobmatch_test TO jobmatch_user;"
   # Grant schema permissions (needed for CREATE TABLE etc.)
   sudo -u postgres psql -d jobmatch -c "GRANT ALL ON SCHEMA public TO jobmatch_user;"
   sudo -u postgres psql -d jobmatch_test -c "GRANT ALL ON SCHEMA public TO jobmatch_user;"
   ```
4. Set environment variable for development:
   ```bash
   echo 'DATABASE_URL=postgresql://jobmatch_user:changeme@localhost:5432/jobmatch' >> .env
   ```

---

## File Map

| Action | File | What changes |
|---|---|---|
| Modify | `requirements.txt` | Add `psycopg2-binary`, `pgvector` |
| Create | `.env.example` | Add `DATABASE_URL`, `TEST_DATABASE_URL`, `OPENAI_API_KEY` |
| Delete | `scripts/migrations/001_create_core_schema.sql` | SQLite-only, superseded by 005 |
| Delete | `scripts/migrations/002_update_job_profiles.sql` | SQLite-only, superseded by 005 |
| Delete | `scripts/migrations/003_rename_axes.sql` | SQLite-only, superseded by 005 |
| Delete | `scripts/migrations/004_add_user_profiles.sql` | SQLite-only, superseded by 005 |
| Create | `scripts/migrations/005_postgres_baseline.sql` | Fresh Postgres-dialect full schema |
| Modify | `src/db.py` | Replace sqlite3 with psycopg2 throughout |
| Modify | `tests/conftest.py` | Replace SQLite temp-file fixture with Postgres fixture |
| Modify | `tests/test_migrations.py` | Update `_column_names` helper to use psycopg2 |
| Modify | `tests/test_db_user_profiles.py` | Update direct `sqlite3.connect()` calls to psycopg2 |
| Modify | `tests/test_extract_resume.py` | Update direct `sqlite3.connect()` calls to psycopg2 |

---

## Task 1: Dependencies and environment config

**Files:**
- Modify: `requirements.txt`
- Create: `.env.example`

- [ ] **Step 1: Add psycopg2-binary and pgvector to requirements.txt**

  Replace the entire file contents with:

  ```
  python-dotenv
  openai
  requests
  pytest
  pytest-cov
  pypdf
  psycopg2-binary
  pgvector
  ```

- [ ] **Step 2: Create .env.example**

  Create the file `/.env.example` at the project root with:

  ```
  OPENAI_API_KEY=sk-...
  DATABASE_URL=postgresql://jobmatch_user:changeme@localhost:5432/jobmatch
  TEST_DATABASE_URL=postgresql://jobmatch_user:changeme@localhost:5432/jobmatch_test
  ```

- [ ] **Step 3: Install dependencies**

  ```bash
  pip install -r requirements.txt
  ```

  Expected: psycopg2-binary and pgvector install without errors.

  Verify psycopg2 works:
  ```bash
  python -c "import psycopg2; print('psycopg2 OK')"
  ```

  Expected: `psycopg2 OK`

- [ ] **Step 4: Commit**

  ```bash
  git add requirements.txt .env.example
  git commit -m "chore(deps): add psycopg2-binary and pgvector"
  ```

---

## Task 2: Create Postgres baseline migration and delete SQLite migrations

**Files:**
- Delete: `scripts/migrations/001_create_core_schema.sql`
- Delete: `scripts/migrations/002_update_job_profiles.sql`
- Delete: `scripts/migrations/003_rename_axes.sql`
- Delete: `scripts/migrations/004_add_user_profiles.sql`
- Create: `scripts/migrations/005_postgres_baseline.sql`

This migration is the authoritative schema for all future development. It reflects the final state after PR 1 (eligible_countries_json and eligible_regions_json are intentionally absent).

- [ ] **Step 1: Delete the four SQLite-specific migrations**

  ```bash
  rm scripts/migrations/001_create_core_schema.sql
  rm scripts/migrations/002_update_job_profiles.sql
  rm scripts/migrations/003_rename_axes.sql
  rm scripts/migrations/004_add_user_profiles.sql
  ```

- [ ] **Step 2: Create scripts/migrations/005_postgres_baseline.sql**

  Create the file with this exact content:

  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;

  CREATE TABLE IF NOT EXISTS schema_migrations (
      filename   TEXT PRIMARY KEY,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );

  CREATE TABLE IF NOT EXISTS job_postings (
      id                       SERIAL PRIMARY KEY,
      source_system            TEXT NOT NULL,
      source_posting_id        TEXT NOT NULL,
      source_url               TEXT,
      title_raw                TEXT,
      company_raw              TEXT,
      location_raw             TEXT,
      posted_date_raw          TEXT,
      source_file              TEXT,
      source_batch             TEXT,
      source_metadata_json     TEXT,
      cleaned_description_text TEXT,
      raw_description_text     TEXT,
      content_hash             TEXT,
      first_seen_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      last_seen_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      imported_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      last_content_changed_at  TIMESTAMPTZ,
      profile_status           TEXT NOT NULL DEFAULT 'missing',
      last_profile_attempt_at  TIMESTAMPTZ,
      last_profile_error       TEXT,
      is_deleted_at_source     INTEGER NOT NULL DEFAULT 0,
      UNIQUE (source_system, source_posting_id)
  );

  CREATE TABLE IF NOT EXISTS job_profiles (
      id                        SERIAL PRIMARY KEY,
      job_posting_id            INTEGER NOT NULL,
      content_hash              TEXT NOT NULL,
      schema_version            TEXT NOT NULL,
      prompt_version            TEXT NOT NULL,
      model_version             TEXT NOT NULL,
      extracted_at              TIMESTAMPTZ NOT NULL,
      extraction_confidence     REAL NOT NULL DEFAULT 0.5,
      is_active                 INTEGER NOT NULL DEFAULT 0,
      invalidated_at            TIMESTAMPTZ,
      invalidated_reason        TEXT,
      profile_json              TEXT NOT NULL,
      normalized_title          TEXT NOT NULL,
      role_family               TEXT NOT NULL,
      seniority                 TEXT NOT NULL,
      employment_type           TEXT NOT NULL,
      work_mode                 TEXT NOT NULL,
      location_scope            TEXT,
      work_auth_required        INTEGER,
      sponsorship_available     INTEGER,
      degree_required           INTEGER,
      years_min_soft            INTEGER,
      years_min_hard            INTEGER,
      salary_min                INTEGER,
      salary_max                INTEGER,
      salary_currency           TEXT,
      salary_period             TEXT,
      salary_tier               INTEGER,
      axis_backend              REAL NOT NULL,
      axis_frontend             REAL NOT NULL,
      axis_platform             REAL NOT NULL,
      axis_ai_data              REAL NOT NULL,
      axis_security_reliability REAL NOT NULL,
      axis_product_ownership    REAL NOT NULL,
      axis_fullstack_span       REAL NOT NULL DEFAULT 0.0,
      FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
      UNIQUE (job_posting_id, content_hash, schema_version, prompt_version, model_version)
  );

  CREATE TABLE IF NOT EXISTS match_results (
      id               SERIAL PRIMARY KEY,
      job_posting_id   INTEGER NOT NULL UNIQUE,
      job_profile_id   INTEGER,
      stage1_score     REAL,
      stage1_decision  TEXT,
      stage1_reasoning TEXT,
      stage2_score     REAL,
      stage2_decision  TEXT,
      stage2_reasoning TEXT,
      FOREIGN KEY (job_posting_id) REFERENCES job_postings(id),
      FOREIGN KEY (job_profile_id) REFERENCES job_profiles(id)
  );

  CREATE TABLE IF NOT EXISTS user_actions (
      id             SERIAL PRIMARY KEY,
      job_posting_id INTEGER NOT NULL,
      status         TEXT,
      notes          TEXT,
      updated_at     TIMESTAMPTZ DEFAULT NOW(),
      FOREIGN KEY (job_posting_id) REFERENCES job_postings(id)
  );

  CREATE TABLE IF NOT EXISTS users (
      id         SERIAL PRIMARY KEY,
      email      TEXT NOT NULL UNIQUE,
      created_at TIMESTAMPTZ DEFAULT NOW()
  );

  CREATE TABLE IF NOT EXISTS user_profiles (
      id                        SERIAL PRIMARY KEY,
      user_id                   INTEGER NOT NULL REFERENCES users(id),
      content_hash              TEXT NOT NULL,
      schema_version            TEXT NOT NULL,
      prompt_version            TEXT NOT NULL,
      model_version             TEXT NOT NULL,
      is_active                 INTEGER NOT NULL DEFAULT 1,
      invalidated_at            TIMESTAMPTZ,
      invalidated_reason        TEXT,
      profile_json              TEXT NOT NULL,
      full_name                 TEXT,
      total_years_experience    REAL,
      current_level             TEXT,
      primary_role_family       TEXT,
      axis_backend              REAL,
      axis_frontend             REAL,
      axis_platform             REAL,
      axis_ai_data              REAL,
      axis_security_reliability REAL,
      axis_product_ownership    REAL,
      axis_fullstack_span       REAL,
      skills_languages          TEXT,
      skills_frameworks         TEXT,
      skills_cloud              TEXT,
      desired_role_families     TEXT,
      desired_seniority         TEXT,
      desired_work_modes        TEXT,
      desired_locations         TEXT,
      desired_salary_min        INTEGER,
      desired_salary_max        INTEGER,
      desired_salary_currency   TEXT,
      work_auth_canada          INTEGER,
      work_auth_us              INTEGER,
      sponsorship_needed        INTEGER,
      degree_level              INTEGER,
      created_at                TIMESTAMPTZ DEFAULT NOW()
  );

  CREATE INDEX IF NOT EXISTS idx_job_postings_status ON job_postings(profile_status);
  CREATE INDEX IF NOT EXISTS idx_job_postings_content_hash ON job_postings(content_hash);
  CREATE INDEX IF NOT EXISTS idx_job_profiles_lookup ON job_profiles(job_posting_id, is_active);
  CREATE INDEX IF NOT EXISTS idx_job_profiles_filters ON job_profiles(role_family, seniority, work_mode, employment_type);
  CREATE UNIQUE INDEX IF NOT EXISTS ux_job_profiles_active ON job_profiles(job_posting_id) WHERE is_active = 1;
  CREATE UNIQUE INDEX IF NOT EXISTS ux_user_profiles_active ON user_profiles(user_id) WHERE is_active = 1;
  ```

- [ ] **Step 3: Verify the migration file has no syntax errors by applying it to the test DB**

  ```bash
  TEST_DATABASE_URL=postgresql://jobmatch_user:changeme@localhost:5432/jobmatch_test
  psql "$TEST_DATABASE_URL" -f scripts/migrations/005_postgres_baseline.sql
  ```

  Expected: commands complete without errors. (`CREATE EXTENSION`, `CREATE TABLE`, `CREATE INDEX` messages.)

  Drop it again so the fixture can recreate it cleanly:
  ```bash
  psql "$TEST_DATABASE_URL" -c "DROP TABLE IF EXISTS match_results, user_actions, user_profiles, users, job_profiles, job_postings, schema_migrations CASCADE;"
  ```

- [ ] **Step 4: Commit**

  ```bash
  git add scripts/migrations/
  git commit -m "refactor(db): replace SQLite migrations with Postgres baseline (005)"
  ```

---

## Task 3: Rewrite db.py and conftest.py for psycopg2

These two files must change together: `db.py` drops `_DB_PATH` (so the old `monkeypatch.setattr(db_module, "_DB_PATH", path)` in conftest would immediately error). Commit both files in one step.

**Files:**
- Modify: `src/db.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Rewrite src/db.py**

  Replace the entire file with:

  ```python
  import hashlib
  import json
  import logging
  import os
  from datetime import datetime, timezone
  from typing import Any

  import psycopg2
  import psycopg2.extras

  from profile_columns import build_profile_columns

  _PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
  _LOG_PATH = os.path.join(_PROJECT_ROOT, "logs", "job_matcher.log")
  _MIGRATIONS_DIR = os.path.join(_PROJECT_ROOT, "scripts", "migrations")

  os.makedirs(os.path.join(_PROJECT_ROOT, "logs"), exist_ok=True)

  logging.basicConfig(
      filename=_LOG_PATH,
      level=logging.INFO,
      format="%(asctime)s - %(levelname)s - %(message)s",
  )

  JOB_PROFILE_COLUMNS = [
      "job_posting_id",
      "content_hash",
      "schema_version",
      "prompt_version",
      "model_version",
      "extracted_at",
      "extraction_confidence",
      "is_active",
      "profile_json",
      "normalized_title",
      "role_family",
      "seniority",
      "employment_type",
      "work_mode",
      "location_scope",
      "work_auth_required",
      "sponsorship_available",
      "degree_required",
      "years_min_soft",
      "years_min_hard",
      "salary_min",
      "salary_max",
      "salary_currency",
      "salary_period",
      "salary_tier",
      "axis_backend",
      "axis_frontend",
      "axis_platform",
      "axis_ai_data",
      "axis_security_reliability",
      "axis_product_ownership",
      "axis_fullstack_span",
  ]

  JOB_PROFILE_UPDATE_COLUMNS = [
      column for column in JOB_PROFILE_COLUMNS
      if column not in {"job_posting_id", "content_hash", "schema_version", "prompt_version", "model_version"}
  ]


  def get_db_connection():
      return psycopg2.connect(
          os.environ["DATABASE_URL"],
          cursor_factory=psycopg2.extras.RealDictCursor,
      )


  def init_db() -> None:
      conn = get_db_connection()
      try:
          apply_schema_migrations(conn)
      finally:
          conn.close()


  def apply_schema_migrations(conn) -> None:
      with conn.cursor() as cur:
          cur.execute(
              """
              CREATE TABLE IF NOT EXISTS schema_migrations (
                  filename   TEXT PRIMARY KEY,
                  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
              )
              """
          )
      conn.commit()

      with conn.cursor() as cur:
          cur.execute("SELECT filename FROM schema_migrations")
          applied = {row["filename"] for row in cur.fetchall()}

      for path in sorted(_migration_paths()):
          filename = os.path.basename(path)
          if filename in applied:
              continue
          with open(path, "r", encoding="utf-8") as handle:
              sql = handle.read()
          with conn.cursor() as cur:
              for stmt in sql.split(";"):
                  stmt = stmt.strip()
                  if stmt and not _is_comment_only(stmt):
                      cur.execute(stmt)
              cur.execute(
                  "INSERT INTO schema_migrations (filename) VALUES (%s)", (filename,)
              )
          conn.commit()


  def _is_comment_only(stmt: str) -> bool:
      return all(
          not line.strip() or line.strip().startswith("--")
          for line in stmt.splitlines()
      )


  def _migration_paths() -> list[str]:
      if not os.path.isdir(_MIGRATIONS_DIR):
          return []
      return [
          os.path.join(_MIGRATIONS_DIR, name)
          for name in os.listdir(_MIGRATIONS_DIR)
          if name.endswith(".sql")
      ]


  def _normalize_text(value: Any) -> str | None:
      if value is None:
          return None
      text = str(value).strip()
      return text or None


  def compute_content_hash(
      title_raw: str | None,
      location_raw: str | None,
      cleaned_description_text: str | None,
  ) -> str | None:
      if not any([title_raw, location_raw, cleaned_description_text]):
          return None
      payload = "||".join([title_raw or "", location_raw or "", cleaned_description_text or ""])
      return hashlib.sha256(payload.encode("utf-8")).hexdigest()


  def _build_source_metadata(row: dict[str, Any]) -> str | None:
      canonical_keys = {
          "job_id", "url", "title", "company", "location",
          "posted_date", "description", "raw_description", "meta_source_file",
      }
      extras = {key: value for key, value in row.items() if key not in canonical_keys}
      return json.dumps(extras, sort_keys=True) if extras else None


  def import_jobs_from_jsonl(jsonl_path: str, source_system: str = "linkedin") -> int:
      source_file = os.path.basename(jsonl_path)
      source_batch = os.path.basename(os.path.dirname(jsonl_path))
      inserted = 0

      conn = get_db_connection()
      cursor = conn.cursor()

      try:
          with open(jsonl_path, "r", encoding="utf-8") as handle:
              for raw_line in handle:
                  if not raw_line.strip():
                      continue
                  row = json.loads(raw_line)
                  source_posting_id = _normalize_text(row.get("job_id"))
                  if not source_posting_id:
                      continue

                  title_raw = _normalize_text(row.get("title"))
                  location_raw = _normalize_text(row.get("location"))
                  cleaned_text = _normalize_text(row.get("description"))
                  content_hash = compute_content_hash(title_raw, location_raw, cleaned_text)

                  cursor.execute(
                      """
                      SELECT id, content_hash, profile_status
                      FROM job_postings
                      WHERE source_system = %s AND source_posting_id = %s
                      """,
                      (source_system, source_posting_id),
                  )
                  existing = cursor.fetchone()

                  if existing is None:
                      cursor.execute(
                          """
                          INSERT INTO job_postings (
                              source_system,
                              source_posting_id,
                              source_url,
                              title_raw,
                              company_raw,
                              location_raw,
                              posted_date_raw,
                              source_file,
                              source_batch,
                              source_metadata_json,
                              cleaned_description_text,
                              raw_description_text,
                              content_hash,
                              first_seen_at,
                              last_seen_at,
                              last_content_changed_at,
                              profile_status,
                              is_deleted_at_source
                          ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                    NOW(), NOW(), NOW(), 'missing', 0)
                          """,
                          (
                              source_system,
                              source_posting_id,
                              _normalize_text(row.get("url")),
                              title_raw,
                              _normalize_text(row.get("company")),
                              location_raw,
                              _normalize_text(row.get("posted_date")),
                              row.get("meta_source_file") or source_file,
                              source_batch,
                              _build_source_metadata(row),
                              cleaned_text,
                              _normalize_text(row.get("raw_description")) or cleaned_text,
                              content_hash,
                          ),
                      )
                      inserted += 1
                      continue

                  content_changed = existing["content_hash"] != content_hash
                  profile_status = existing["profile_status"]
                  if content_changed:
                      profile_status = "stale" if profile_status == "current" else "missing"

                  cursor.execute(
                      """
                      UPDATE job_postings
                      SET source_url               = %s,
                          title_raw                = %s,
                          company_raw              = %s,
                          location_raw             = %s,
                          posted_date_raw          = %s,
                          source_file              = %s,
                          source_batch             = %s,
                          source_metadata_json     = %s,
                          cleaned_description_text = %s,
                          raw_description_text     = %s,
                          content_hash             = %s,
                          last_seen_at             = NOW(),
                          updated_at               = NOW(),
                          last_content_changed_at  = CASE WHEN %s THEN NOW() ELSE last_content_changed_at END,
                          profile_status           = %s,
                          is_deleted_at_source     = 0
                      WHERE id = %s
                      """,
                      (
                          _normalize_text(row.get("url")),
                          title_raw,
                          _normalize_text(row.get("company")),
                          location_raw,
                          _normalize_text(row.get("posted_date")),
                          row.get("meta_source_file") or source_file,
                          source_batch,
                          _build_source_metadata(row),
                          cleaned_text,
                          _normalize_text(row.get("raw_description")) or cleaned_text,
                          content_hash,
                          content_changed,
                          profile_status,
                          existing["id"],
                      ),
                  )

          conn.commit()
          logging.info("Imported %s new jobs from %s", inserted, source_file)
          return inserted
      except Exception:
          conn.rollback()
          logging.exception("Error importing %s", jsonl_path)
          raise
      finally:
          cursor.close()
          conn.close()


  def get_pending_extraction(
      schema_version: str | None = None,
      prompt_version: str | None = None,
      model_version: str | None = None,
  ):
      mismatch_conditions = [
          "ap.id IS NULL",
          "jp.profile_status IN ('missing', 'stale', 'failed')",
          "ap.content_hash <> jp.content_hash",
      ]
      params: list[Any] = []

      if schema_version is not None:
          mismatch_conditions.append("ap.schema_version <> %s")
          params.append(schema_version)
      if prompt_version is not None:
          mismatch_conditions.append("ap.prompt_version <> %s")
          params.append(prompt_version)
      if model_version is not None:
          mismatch_conditions.append("ap.model_version <> %s")
          params.append(model_version)

      conn = get_db_connection()
      cursor = conn.cursor()
      cursor.execute(
          f"""
          SELECT
              jp.id AS job_posting_id,
              jp.source_posting_id AS source_id,
              jp.cleaned_description_text AS raw_text,
              jp.content_hash,
              jp.profile_status
          FROM job_postings jp
          LEFT JOIN job_profiles ap
              ON ap.job_posting_id = jp.id
             AND ap.is_active = 1
          WHERE jp.cleaned_description_text IS NOT NULL
            AND ({" OR ".join(mismatch_conditions)})
          ORDER BY jp.id
          """,
          params,
      )
      rows = [dict(row) for row in cursor.fetchall()]
      cursor.close()
      conn.close()
      return rows


  def save_extraction(job_posting_id: int, profile) -> None:
      payload = profile.model_dump()
      conn = get_db_connection()
      cursor = conn.cursor()

      try:
          cursor.execute(
              "SELECT content_hash FROM job_postings WHERE id = %s", (job_posting_id,)
          )
          posting = cursor.fetchone()
          if posting is None:
              raise RuntimeError(f"Unknown job_posting_id {job_posting_id}")
          if not posting["content_hash"]:
              raise RuntimeError(f"Missing content_hash for job_posting_id {job_posting_id}")

          columns = build_profile_columns(
              payload,
              job_posting_id=job_posting_id,
              content_hash=posting["content_hash"],
          )
          columns["extracted_at"] = columns["extracted_at"] or datetime.now(timezone.utc).isoformat()
          columns["is_active"] = 1

          cursor.execute(
              """
              UPDATE job_profiles
              SET is_active = 0,
                  invalidated_at = NOW(),
                  invalidated_reason = 'superseded'
              WHERE job_posting_id = %s
                AND is_active = 1
                AND NOT (
                    content_hash = %s
                    AND schema_version = %s
                    AND prompt_version = %s
                    AND model_version = %s
                )
              """,
              (
                  job_posting_id,
                  columns["content_hash"],
                  columns["schema_version"],
                  columns["prompt_version"],
                  columns["model_version"],
              ),
          )

          _upsert_job_profile(cursor, columns)

          cursor.execute(
              """
              UPDATE job_postings
              SET profile_status = 'current',
                  last_profile_attempt_at = NOW(),
                  last_profile_error = NULL,
                  updated_at = NOW()
              WHERE id = %s
              """,
              (job_posting_id,),
          )

          conn.commit()
          logging.info("Saved extraction for job_posting_id: %s", job_posting_id)
      except Exception:
          conn.rollback()
          raise
      finally:
          cursor.close()
          conn.close()


  def _upsert_job_profile(cursor, columns: dict[str, Any]) -> None:
      column_sql = ", ".join(JOB_PROFILE_COLUMNS)
      placeholders = ", ".join(["%s"] * len(JOB_PROFILE_COLUMNS))
      update_sql = ", ".join([f"{col} = EXCLUDED.{col}" for col in JOB_PROFILE_UPDATE_COLUMNS])
      cursor.execute(
          f"""
          INSERT INTO job_profiles ({column_sql})
          VALUES ({placeholders})
          ON CONFLICT(job_posting_id, content_hash, schema_version, prompt_version, model_version)
          DO UPDATE SET {update_sql},
                        invalidated_at = NULL,
                        invalidated_reason = NULL
          """,
          [columns[col] for col in JOB_PROFILE_COLUMNS],
      )


  def fail_extraction(job_posting_id: int, error: str) -> None:
      conn = get_db_connection()
      cursor = conn.cursor()
      cursor.execute(
          """
          UPDATE job_postings
          SET profile_status = 'failed',
              last_profile_attempt_at = NOW(),
              last_profile_error = %s,
              updated_at = NOW()
          WHERE id = %s
          """,
          (error, job_posting_id),
      )
      conn.commit()
      cursor.close()
      conn.close()
      logging.warning("Extraction failed for job_posting_id %s: %s", job_posting_id, error)


  def get_active_job_profile(job_posting_id: int) -> dict[str, Any] | None:
      conn = get_db_connection()
      cursor = conn.cursor()
      cursor.execute(
          """
          SELECT *
          FROM job_profiles
          WHERE job_posting_id = %s
            AND is_active = 1
          """,
          (job_posting_id,),
      )
      row = cursor.fetchone()
      cursor.close()
      conn.close()
      return dict(row) if row is not None else None


  def get_or_create_user(email: str) -> int:
      conn = get_db_connection()
      cursor = conn.cursor()
      try:
          cursor.execute(
              "INSERT INTO users (email) VALUES (%s) ON CONFLICT (email) DO NOTHING",
              (email,),
          )
          conn.commit()
          cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
          return cursor.fetchone()["id"]
      finally:
          cursor.close()
          conn.close()


  def get_active_user_profile(user_id: int) -> dict | None:
      conn = get_db_connection()
      cursor = conn.cursor()
      try:
          cursor.execute(
              "SELECT * FROM user_profiles WHERE user_id = %s AND is_active = 1",
              (user_id,),
          )
          row = cursor.fetchone()
          return dict(row) if row is not None else None
      finally:
          cursor.close()
          conn.close()


  def save_resume_extraction(user_id: int, profile, columns: dict, *, content_hash: str) -> None:
      fixed = {
          "user_id": user_id,
          "content_hash": content_hash,
          "schema_version": profile.meta.schema_version,
          "prompt_version": profile.meta.prompt_version,
          "model_version": profile.meta.model,
          "is_active": 1,
          "profile_json": profile.model_dump_json(),
      }
      all_cols = {**fixed, **columns}
      col_names = list(all_cols.keys())
      col_sql = ", ".join(col_names)
      placeholders = ", ".join(["%s"] * len(col_names))

      conn = get_db_connection()
      cursor = conn.cursor()
      try:
          cursor.execute(
              """
              UPDATE user_profiles
              SET is_active = 0,
                  invalidated_at = NOW(),
                  invalidated_reason = 'superseded'
              WHERE user_id = %s AND is_active = 1
              """,
              (user_id,),
          )
          cursor.execute(
              f"INSERT INTO user_profiles ({col_sql}) VALUES ({placeholders})",
              [all_cols[c] for c in col_names],
          )
          conn.commit()
          logging.info("Saved resume extraction for user_id: %s", user_id)
      except Exception:
          conn.rollback()
          raise
      finally:
          cursor.close()
          conn.close()


  def get_jobs_for_stage1():
      conn = get_db_connection()
      cursor = conn.cursor()
      cursor.execute(
          """
          SELECT
              jp.id,
              jp.source_posting_id AS source_id,
              jp.title_raw AS title,
              jp.company_raw AS company,
              ap.id AS job_profile_id,
              ap.profile_json
          FROM job_postings jp
          JOIN job_profiles ap
            ON ap.job_posting_id = jp.id
           AND ap.is_active = 1
          LEFT JOIN match_results mr
            ON mr.job_posting_id = jp.id
          WHERE mr.id IS NULL
          """
      )
      rows = [dict(row) for row in cursor.fetchall()]
      cursor.close()
      conn.close()
      return rows


  def save_stage1_result(
      job_posting_id: int, score: float, decision: str, reasoning: str
  ) -> None:
      active_profile = get_active_job_profile(job_posting_id)
      conn = get_db_connection()
      cursor = conn.cursor()
      cursor.execute(
          """
          INSERT INTO match_results (job_posting_id, job_profile_id, stage1_score, stage1_decision, stage1_reasoning)
          VALUES (%s, %s, %s, %s, %s)
          ON CONFLICT(job_posting_id) DO UPDATE SET
              job_profile_id = EXCLUDED.job_profile_id,
              stage1_score = EXCLUDED.stage1_score,
              stage1_decision = EXCLUDED.stage1_decision,
              stage1_reasoning = EXCLUDED.stage1_reasoning
          """,
          (
              job_posting_id,
              active_profile["id"] if active_profile else None,
              score,
              decision,
              reasoning,
          ),
      )
      conn.commit()
      cursor.close()
      conn.close()


  def get_jobs_for_stage2():
      conn = get_db_connection()
      cursor = conn.cursor()
      cursor.execute(
          """
          SELECT
              jp.id,
              jp.source_posting_id AS source_id,
              jp.title_raw AS title,
              jp.company_raw AS company,
              ap.id AS job_profile_id,
              ap.profile_json,
              mr.stage1_score
          FROM job_postings jp
          JOIN job_profiles ap
            ON ap.job_posting_id = jp.id
           AND ap.is_active = 1
          JOIN match_results mr
            ON mr.job_posting_id = jp.id
          WHERE mr.stage1_decision = 'advance'
            AND mr.stage2_score IS NULL
          """
      )
      rows = [dict(row) for row in cursor.fetchall()]
      cursor.close()
      conn.close()
      return rows


  def save_stage2_result(
      job_posting_id: int, score: float, decision: str, reasoning: str
  ) -> None:
      active_profile = get_active_job_profile(job_posting_id)
      conn = get_db_connection()
      cursor = conn.cursor()
      cursor.execute(
          """
          UPDATE match_results
          SET job_profile_id = %s,
              stage2_score = %s,
              stage2_decision = %s,
              stage2_reasoning = %s
          WHERE job_posting_id = %s
          """,
          (
              active_profile["id"] if active_profile else None,
              score,
              decision,
              reasoning,
              job_posting_id,
          ),
      )
      conn.commit()
      cursor.close()
      conn.close()


  def get_top_matches(limit: int = 10):
      conn = get_db_connection()
      cursor = conn.cursor()
      cursor.execute(
          """
          SELECT
              jp.title_raw AS title,
              jp.company_raw AS company,
              jp.source_url AS url,
              mr.stage2_score AS score,
              mr.stage2_decision AS decision,
              mr.stage2_reasoning AS reasoning
          FROM job_postings jp
          JOIN match_results mr
            ON mr.job_posting_id = jp.id
          WHERE mr.stage2_decision IS NOT NULL
          ORDER BY mr.stage2_score DESC
          LIMIT %s
          """,
          (limit,),
      )
      rows = [dict(row) for row in cursor.fetchall()]
      cursor.close()
      conn.close()
      return rows
  ```

- [ ] **Step 2: Rewrite tests/conftest.py**

  Replace the entire file with:

  ```python
  import os
  import sys
  from pathlib import Path

  import pytest

  os.environ.setdefault("OPENAI_API_KEY", "test-sk-dummy")

  ROOT = Path(__file__).resolve().parent.parent
  sys.path.insert(0, str(ROOT / "src"))
  sys.path.insert(0, str(ROOT))

  _TEST_DB_URL = os.environ.get(
      "TEST_DATABASE_URL", "postgresql://localhost/jobmatch_test"
  )


  def _drop_all_tables(url: str) -> None:
      import psycopg2

      conn = psycopg2.connect(url)
      try:
          with conn.cursor() as cur:
              cur.execute(
                  """
                  DROP TABLE IF EXISTS
                      match_results, user_actions, user_profiles, users,
                      job_profiles, job_postings, schema_migrations
                  CASCADE
                  """
              )
          conn.commit()
      finally:
          conn.close()


  @pytest.fixture
  def temp_db(monkeypatch):
      """Yields a Postgres DATABASE_URL with a fresh schema and all migrations applied."""
      import db as db_module

      monkeypatch.setenv("DATABASE_URL", _TEST_DB_URL)
      _drop_all_tables(_TEST_DB_URL)
      db_module.init_db()

      yield _TEST_DB_URL

      _drop_all_tables(_TEST_DB_URL)
  ```

- [ ] **Step 3: Run the test suite — expect most tests to pass**

  ```bash
  pytest tests/ -v
  ```

  Expected: all tests that don't use raw `sqlite3` connections pass. You'll see failures only in `test_migrations.py`, `test_db_user_profiles.py`, and `test_extract_resume.py` — those are fixed in Task 4.

  If you see `psycopg2.OperationalError: could not connect to server`, verify `TEST_DATABASE_URL` is set correctly and Postgres is running.

- [ ] **Step 4: Commit**

  ```bash
  git add src/db.py tests/conftest.py
  git commit -m "refactor(db): replace sqlite3 with psycopg2, read DATABASE_URL from env"
  ```

---

## Task 4: Update DB-touching tests to use psycopg2

The three test files use `sqlite3.connect(temp_db)` directly. With the new fixture, `temp_db` is a URL string (`postgresql://...`). Replace all direct sqlite3 usage with psycopg2.

**Files:**
- Modify: `tests/test_migrations.py`
- Modify: `tests/test_db_user_profiles.py`
- Modify: `tests/test_extract_resume.py`

- [ ] **Step 1: Rewrite tests/test_migrations.py**

  Replace the entire file with:

  ```python
  def _column_names(database_url, table):
      import psycopg2

      conn = psycopg2.connect(database_url)
      try:
          with conn.cursor() as cur:
              cur.execute(
                  """
                  SELECT column_name
                  FROM information_schema.columns
                  WHERE table_name = %s AND table_schema = 'public'
                  """,
                  (table,),
              )
              return [r[0] for r in cur.fetchall()]
      finally:
          conn.close()


  def test_axis_columns_use_canonical_names(temp_db):
      cols = _column_names(temp_db, "job_profiles")
      assert "axis_platform" in cols
      assert "axis_product_ownership" in cols
      assert "axis_platform_cloud" not in cols
      assert "axis_product_sense" not in cols


  def test_axis_fullstack_span_column_still_exists(temp_db):
      cols = _column_names(temp_db, "job_profiles")
      assert "axis_fullstack_span" in cols
  ```

- [ ] **Step 2: Run test_migrations.py — must PASS**

  ```bash
  pytest tests/test_migrations.py -v
  ```

  Expected: both tests PASS.

- [ ] **Step 3: Rewrite tests/test_db_user_profiles.py**

  Replace the entire file with:

  ```python
  import pytest


  def _column_names(database_url, table):
      import psycopg2

      conn = psycopg2.connect(database_url)
      try:
          with conn.cursor() as cur:
              cur.execute(
                  """
                  SELECT column_name
                  FROM information_schema.columns
                  WHERE table_name = %s AND table_schema = 'public'
                  """,
                  (table,),
              )
              return [r[0] for r in cur.fetchall()]
      finally:
          conn.close()


  def test_users_table_exists(temp_db):
      cols = _column_names(temp_db, "users")
      assert "id" in cols
      assert "email" in cols
      assert "created_at" in cols


  def test_user_profiles_table_exists(temp_db):
      cols = _column_names(temp_db, "user_profiles")
      expected = [
          "id", "user_id", "content_hash", "schema_version", "prompt_version",
          "model_version", "is_active", "invalidated_at", "invalidated_reason", "profile_json",
          "full_name", "total_years_experience", "current_level", "primary_role_family",
          "axis_backend", "axis_frontend", "axis_platform", "axis_ai_data",
          "axis_security_reliability", "axis_product_ownership", "axis_fullstack_span",
          "skills_languages", "skills_frameworks", "skills_cloud",
          "desired_role_families", "desired_seniority", "desired_work_modes",
          "desired_locations", "desired_salary_min", "desired_salary_max",
          "desired_salary_currency", "work_auth_canada", "work_auth_us",
          "sponsorship_needed", "degree_level", "created_at",
      ]
      for col in expected:
          assert col in cols, f"missing column: {col}"


  def _make_user_profile():
      from models.user_profile import (
          UserProfile, ResumeSkills,
          ResumeEducation, CareerPreferences, ResumeWorkAuth,
      )
      from models.job_profile import ProfileMeta, Axes
      return UserProfile(
          meta=ProfileMeta(
              schema_version="1.0", prompt_version="1.0",
              model="gpt-4.1-nano", generated_at="2026-05-07T00:00:00+00:00",
          ),
          full_name="Test User",
          total_years_experience=2.0,
          current_level="junior",
          primary_role_family="backend",
          axes=Axes(
              axis_backend=0.5, axis_frontend=0.1, axis_platform=0.2,
              axis_ai_data=0.1, axis_security_reliability=0.2, axis_product_ownership=0.1,
          ),
          skills=ResumeSkills(
              languages=["Python"], frameworks=[], cloud=[], databases=[],
              devops=[], ai_ml=[], other_tools=[], concepts=[],
          ),
          work_experience=[],
          education=ResumeEducation(degree_level=1, fields=["CS"]),
          preferences=CareerPreferences(
              desired_roles=[], desired_role_families=["backend"],
              desired_seniority="mid", desired_work_modes=["remote"],
              desired_locations=[], desired_salary_min=None,
              desired_salary_max=None, desired_salary_currency="CAD",
          ),
          work_auth=ResumeWorkAuth(canada=True, us=False, sponsorship_needed=None),
          extraction_confidence=0.8,
          evidence_snippets=[],
      )


  def test_get_or_create_user_idempotent(temp_db):
      import db
      user_id_1 = db.get_or_create_user("alice@example.com")
      user_id_2 = db.get_or_create_user("alice@example.com")
      assert isinstance(user_id_1, int)
      assert user_id_1 == user_id_2


  def test_get_or_create_user_different_emails(temp_db):
      import db
      id_a = db.get_or_create_user("alice@example.com")
      id_b = db.get_or_create_user("bob@example.com")
      assert id_a != id_b


  def test_get_active_user_profile_returns_none_when_empty(temp_db):
      import db
      user_id = db.get_or_create_user("alice@example.com")
      result = db.get_active_user_profile(user_id)
      assert result is None


  def test_save_resume_extraction_stores_row(temp_db):
      import psycopg2
      import psycopg2.extras
      import db
      from user_profile_columns import build_profile_columns

      user_id = db.get_or_create_user("alice@example.com")
      profile = _make_user_profile()
      db.save_resume_extraction(user_id, profile, build_profile_columns(profile), content_hash="abc123")

      conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
      try:
          with conn.cursor() as cur:
              cur.execute(
                  "SELECT * FROM user_profiles WHERE user_id = %s AND is_active = 1",
                  (user_id,),
              )
              row = cur.fetchone()
          assert row is not None
          assert row["current_level"] == "junior"
          assert row["content_hash"] == "abc123"
          assert row["is_active"] == 1
      finally:
          conn.close()


  def test_get_active_user_profile_returns_row_after_save(temp_db):
      import db
      from user_profile_columns import build_profile_columns

      user_id = db.get_or_create_user("alice@example.com")
      profile = _make_user_profile()
      db.save_resume_extraction(user_id, profile, build_profile_columns(profile), content_hash="abc123")

      result = db.get_active_user_profile(user_id)
      assert result is not None
      assert result["content_hash"] == "abc123"


  def test_versioning_supersedes_old_row(temp_db):
      import psycopg2
      import psycopg2.extras
      import db
      from user_profile_columns import build_profile_columns

      user_id = db.get_or_create_user("alice@example.com")
      profile = _make_user_profile()

      db.save_resume_extraction(user_id, profile, build_profile_columns(profile), content_hash="hash_v1")
      db.save_resume_extraction(user_id, profile, build_profile_columns(profile), content_hash="hash_v2")

      conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
      try:
          with conn.cursor() as cur:
              cur.execute("SELECT * FROM user_profiles WHERE user_id = %s", (user_id,))
              rows = cur.fetchall()
          assert len(rows) == 2
          active = [r for r in rows if r["is_active"] == 1]
          inactive = [r for r in rows if r["is_active"] == 0]
          assert len(active) == 1
          assert len(inactive) == 1
          assert inactive[0]["invalidated_reason"] == "superseded"
          assert active[0]["content_hash"] == "hash_v2"
      finally:
          conn.close()


  def test_unique_index_prevents_two_active_profiles(temp_db):
      import psycopg2
      import psycopg2.extras

      conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
      try:
          with conn.cursor() as cur:
              cur.execute("INSERT INTO users (email) VALUES ('test@example.com')")
              conn.commit()
              cur.execute("SELECT id FROM users WHERE email = 'test@example.com'")
              user_id = cur.fetchone()["id"]

              cur.execute(
                  """
                  INSERT INTO user_profiles
                      (user_id, content_hash, schema_version, prompt_version, model_version,
                       is_active, profile_json)
                  VALUES (%s, 'h1', '1.0', '1.0', 'model', 1, '{}')
                  """,
                  (user_id,),
              )
              conn.commit()

              with pytest.raises(psycopg2.IntegrityError):
                  cur.execute(
                      """
                      INSERT INTO user_profiles
                          (user_id, content_hash, schema_version, prompt_version, model_version,
                           is_active, profile_json)
                      VALUES (%s, 'h2', '1.0', '1.0', 'model', 1, '{}')
                      """,
                      (user_id,),
                  )
                  conn.commit()
              conn.rollback()
      finally:
          conn.close()
  ```

- [ ] **Step 4: Run test_db_user_profiles.py — must PASS**

  ```bash
  pytest tests/test_db_user_profiles.py -v
  ```

  Expected: all tests PASS.

- [ ] **Step 5: Update the raw DB inspection calls in tests/test_extract_resume.py**

  In `tests/test_extract_resume.py`, find the two tests that open a direct `sqlite3` connection. Replace those sections as follows.

  In `test_extract_resume_saves_profile_with_denormalized_columns`, replace:

  ```python
      conn = sqlite3.connect(temp_db)
      conn.row_factory = sqlite3.Row
      try:
          user = conn.execute(
              "SELECT * FROM users WHERE email = 'jane@example.com'"
          ).fetchone()
          assert user is not None

          profile = conn.execute(
              "SELECT * FROM user_profiles WHERE user_id = ? AND is_active = 1",
              (user["id"],),
          ).fetchone()
          assert profile is not None
          assert profile["current_level"] == "junior"
          assert profile["primary_role_family"] == "backend"
          assert profile["axis_backend"] == pytest.approx(0.7)
          assert profile["axis_fullstack_span"] == pytest.approx(0.20)  # 2*min(0.7,0.1)
          assert profile["work_auth_canada"] == 1
          assert profile["work_auth_us"] == 0
          assert profile["degree_level"] == 1

          profile_json = json.loads(profile["profile_json"])
          assert profile_json["full_name"] == "Jane Doe"
          assert profile_json["extraction_confidence"] == pytest.approx(0.85)
      finally:
          conn.close()
  ```

  With:

  ```python
      import psycopg2
      import psycopg2.extras

      conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
      try:
          with conn.cursor() as cur:
              cur.execute("SELECT * FROM users WHERE email = 'jane@example.com'")
              user = cur.fetchone()
          assert user is not None

          with conn.cursor() as cur:
              cur.execute(
                  "SELECT * FROM user_profiles WHERE user_id = %s AND is_active = 1",
                  (user["id"],),
              )
              profile = cur.fetchone()
          assert profile is not None
          assert profile["current_level"] == "junior"
          assert profile["primary_role_family"] == "backend"
          assert profile["axis_backend"] == pytest.approx(0.7)
          assert profile["axis_fullstack_span"] == pytest.approx(0.20)
          assert profile["work_auth_canada"] == 1
          assert profile["work_auth_us"] == 0
          assert profile["degree_level"] == 1

          profile_json = json.loads(profile["profile_json"])
          assert profile_json["full_name"] == "Jane Doe"
          assert profile_json["extraction_confidence"] == pytest.approx(0.85)
      finally:
          conn.close()
  ```

  In `test_extract_resume_persists_personal_projects_in_profile_json`, replace:

  ```python
      conn = sqlite3.connect(temp_db)
      conn.row_factory = sqlite3.Row
      try:
          user = conn.execute("SELECT id FROM users WHERE email = 'projects@example.com'").fetchone()
          assert user is not None
          row = conn.execute(
              "SELECT profile_json FROM user_profiles WHERE user_id = ? AND is_active = 1",
              (user["id"],),
          ).fetchone()
          assert row is not None
          profile_json = json.loads(row["profile_json"])
          projects = profile_json.get("personal_projects", [])
          assert len(projects) == 1
          assert projects[0]["name"] == "open-source-tool"
          assert "SQLite" in projects[0]["tech_stack"]
      finally:
          conn.close()
  ```

  With:

  ```python
      import psycopg2
      import psycopg2.extras

      conn = psycopg2.connect(temp_db, cursor_factory=psycopg2.extras.RealDictCursor)
      try:
          with conn.cursor() as cur:
              cur.execute("SELECT id FROM users WHERE email = 'projects@example.com'")
              user = cur.fetchone()
          assert user is not None
          with conn.cursor() as cur:
              cur.execute(
                  "SELECT profile_json FROM user_profiles WHERE user_id = %s AND is_active = 1",
                  (user["id"],),
              )
              row = cur.fetchone()
          assert row is not None
          profile_json = json.loads(row["profile_json"])
          projects = profile_json.get("personal_projects", [])
          assert len(projects) == 1
          assert projects[0]["name"] == "open-source-tool"
          assert "SQLite" in projects[0]["tech_stack"]
      finally:
          conn.close()
  ```

  Also remove the `import sqlite3` lines from both test functions (they appear at the top of each test body).

- [ ] **Step 6: Run the full test suite — all tests must PASS**

  ```bash
  pytest tests/ -v
  ```

  Expected: all tests PASS. No `sqlite3` references should remain in any test assertion or import (grep to verify):

  ```bash
  grep -r "sqlite3" tests/
  ```

  Expected: no output.

- [ ] **Step 7: Commit**

  ```bash
  git add tests/test_migrations.py tests/test_db_user_profiles.py tests/test_extract_resume.py
  git commit -m "test: update DB-touching tests from sqlite3 to psycopg2"
  ```

---

## Task 5: Final verification

- [ ] **Step 1: Verify no sqlite3 references remain in src/**

  ```bash
  grep -r "sqlite3" src/
  ```

  Expected: no output.

- [ ] **Step 2: Run the full test suite one final time**

  ```bash
  pytest tests/ -v
  ```

  Expected: all tests PASS (same count as before).

- [ ] **Step 3: Smoke-test init_db against the application DB**

  ```bash
  python -c "
  import os, sys
  sys.path.insert(0, 'src')
  os.environ['DATABASE_URL'] = 'postgresql://jobmatch_user:changeme@localhost:5432/jobmatch'
  import db
  db.init_db()
  print('init_db OK — migration 005 applied')
  "
  ```

  Expected: `init_db OK — migration 005 applied`

- [ ] **Step 4: Verify DoD from TODO_LIST.md**

  - `pytest tests/ -v` passes against Postgres ✓ (Step 2)
  - Full pipeline (`ingest → extract`) can run end-to-end on Postgres. Smoke-test:
    ```bash
    python -c "
    import os, sys
    sys.path.insert(0, 'src')
    os.environ['DATABASE_URL'] = 'postgresql://jobmatch_user:changeme@localhost:5432/jobmatch'
    import db
    print('get_or_create_user:', db.get_or_create_user('test@example.com'))
    print('get_pending_extraction:', db.get_pending_extraction()[:1])
    print('Postgres pipeline OK')
    "
    ```
    Expected: prints user id and empty or populated list, no exceptions.
  - SQLite files are no longer referenced in `src/`:
    ```bash
    grep -r "sqlite3\|_DB_PATH" src/
    ```
    Expected: no output.
