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


def save_extraction(job_posting_id: int, profile) -> int:
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

        job_profile_id = _upsert_job_profile(cursor, columns)

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
        return job_profile_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def _upsert_job_profile(cursor, columns: dict[str, Any]) -> int:
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
        RETURNING id
        """,
        [columns[col] for col in JOB_PROFILE_COLUMNS],
    )
    row = cursor.fetchone()
    return row["id"]


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


def save_resume_extraction(user_id: int, profile, columns: dict, *, content_hash: str) -> int:
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
            f"INSERT INTO user_profiles ({col_sql}) VALUES ({placeholders}) RETURNING id",
            [all_cols[c] for c in col_names],
        )
        user_profile_id = cursor.fetchone()["id"]
        conn.commit()
        logging.info("Saved resume extraction for user_id: %s", user_id)
        return user_profile_id
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


def save_job_profile_skills(
    job_profile_id: int,
    entries: list[tuple[int, str, int | None]],
    conn,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM job_profile_skills WHERE job_profile_id = %s",
            (job_profile_id,),
        )
        if entries:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO job_profile_skills (job_profile_id, skill_id, importance, group_id) VALUES %s",
                [(job_profile_id, skill_id, importance, group_id) for skill_id, importance, group_id in entries],
            )


def save_resume_skills(
    user_profile_id: int,
    entries: list[tuple[int, str]],
    conn,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM resume_skills WHERE resume_id = %s",
            (user_profile_id,),
        )
        if entries:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO resume_skills (resume_id, skill_id, importance) VALUES %s",
                [(user_profile_id, skill_id, importance) for skill_id, importance in entries],
            )


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
