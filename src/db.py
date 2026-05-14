import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from profile_columns import build_profile_columns

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LOG_PATH = os.path.join(_PROJECT_ROOT, "logs", "job_matcher.log")
_DB_PATH = os.path.join(_PROJECT_ROOT, "data", "job_matcher.db")
_MIGRATIONS_DIR = os.path.join(_PROJECT_ROOT, "scripts", "migrations")

os.makedirs(os.path.join(_PROJECT_ROOT, "logs"), exist_ok=True)
os.makedirs(os.path.join(_PROJECT_ROOT, "data"), exist_ok=True)

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
    "eligible_countries_json",
    "eligible_regions_json",
]

JOB_PROFILE_UPDATE_COLUMNS = [column for column in JOB_PROFILE_COLUMNS if column not in {"job_posting_id", "content_hash", "schema_version", "prompt_version", "model_version"}]


def get_db_connection():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_db_connection()
    try:
        apply_schema_migrations(conn)
    finally:
        conn.close()


def apply_schema_migrations(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename   TEXT PRIMARY KEY,
            applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    applied = {
        row[0]
        for row in conn.execute("SELECT filename FROM schema_migrations").fetchall()
    }
    for path in sorted(_migration_paths()):
        filename = os.path.basename(path)
        if filename in applied:
            continue
        with open(path, "r", encoding="utf-8") as handle:
            conn.executescript(handle.read())
        conn.execute(
            "INSERT INTO schema_migrations (filename) VALUES (?)", (filename,)
        )
    conn.commit()


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


def compute_content_hash(title_raw: str | None, location_raw: str | None, cleaned_description_text: str | None) -> str | None:
    if not any([title_raw, location_raw, cleaned_description_text]):
        return None
    payload = "||".join([title_raw or "", location_raw or "", cleaned_description_text or ""])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_source_metadata(row: dict[str, Any]) -> str | None:
    canonical_keys = {
        "job_id",
        "url",
        "title",
        "company",
        "location",
        "posted_date",
        "description",
        "raw_description",
        "meta_source_file",
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
                    WHERE source_system = ? AND source_posting_id = ?
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
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'missing', 0)
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
                    SET source_url               = ?,
                        title_raw                = ?,
                        company_raw              = ?,
                        location_raw             = ?,
                        posted_date_raw          = ?,
                        source_file              = ?,
                        source_batch             = ?,
                        source_metadata_json     = ?,
                        cleaned_description_text = ?,
                        raw_description_text     = ?,
                        content_hash             = ?,
                        last_seen_at             = CURRENT_TIMESTAMP,
                        updated_at               = CURRENT_TIMESTAMP,
                        last_content_changed_at  = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE last_content_changed_at END,
                        profile_status           = ?,
                        is_deleted_at_source     = 0
                    WHERE id = ?
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
                        1 if content_changed else 0,
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
        mismatch_conditions.append("ap.schema_version <> ?")
        params.append(schema_version)
    if prompt_version is not None:
        mismatch_conditions.append("ap.prompt_version <> ?")
        params.append(prompt_version)
    if model_version is not None:
        mismatch_conditions.append("ap.model_version <> ?")
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
        cursor.execute("SELECT content_hash FROM job_postings WHERE id = ?", (job_posting_id,))
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
                invalidated_at = CURRENT_TIMESTAMP,
                invalidated_reason = 'superseded'
            WHERE job_posting_id = ?
              AND is_active = 1
              AND NOT (
                  content_hash = ?
                  AND schema_version = ?
                  AND prompt_version = ?
                  AND model_version = ?
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
                last_profile_attempt_at = CURRENT_TIMESTAMP,
                last_profile_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
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


def _upsert_job_profile(cursor: sqlite3.Cursor, columns: dict[str, Any]) -> None:
    column_sql = ", ".join(JOB_PROFILE_COLUMNS)
    placeholders = ", ".join(["?"] * len(JOB_PROFILE_COLUMNS))
    update_sql = ", ".join([f"{column} = excluded.{column}" for column in JOB_PROFILE_UPDATE_COLUMNS])
    cursor.execute(
        f"""
        INSERT INTO job_profiles ({column_sql})
        VALUES ({placeholders})
        ON CONFLICT(job_posting_id, content_hash, schema_version, prompt_version, model_version)
        DO UPDATE SET {update_sql},
                      invalidated_at = NULL,
                      invalidated_reason = NULL
        """,
        [columns[column] for column in JOB_PROFILE_COLUMNS],
    )


def fail_extraction(job_posting_id: int, error: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE job_postings
        SET profile_status = 'failed',
            last_profile_attempt_at = CURRENT_TIMESTAMP,
            last_profile_error = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
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
        WHERE job_posting_id = ?
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
            "INSERT OR IGNORE INTO users (email) VALUES (?)",
            (email,),
        )
        conn.commit()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        return cursor.fetchone()["id"]
    finally:
        cursor.close()
        conn.close()


def get_active_user_profile(user_id: int) -> dict | None:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM user_profiles WHERE user_id = ? AND is_active = 1",
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
    placeholders = ", ".join(["?"] * len(col_names))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE user_profiles
            SET is_active = 0,
                invalidated_at = CURRENT_TIMESTAMP,
                invalidated_reason = 'superseded'
            WHERE user_id = ? AND is_active = 1
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


def save_stage1_result(job_posting_id: int, score: float, decision: str, reasoning: str) -> None:
    active_profile = get_active_job_profile(job_posting_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO match_results (job_posting_id, job_profile_id, stage1_score, stage1_decision, stage1_reasoning)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(job_posting_id) DO UPDATE SET
            job_profile_id = excluded.job_profile_id,
            stage1_score = excluded.stage1_score,
            stage1_decision = excluded.stage1_decision,
            stage1_reasoning = excluded.stage1_reasoning
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


def save_stage2_result(job_posting_id: int, score: float, decision: str, reasoning: str) -> None:
    active_profile = get_active_job_profile(job_posting_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE match_results
        SET job_profile_id = ?,
            stage2_score = ?,
            stage2_decision = ?,
            stage2_reasoning = ?
        WHERE job_posting_id = ?
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
        LIMIT ?
        """,
        (limit,),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return rows
