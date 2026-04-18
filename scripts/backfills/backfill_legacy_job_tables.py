import argparse
import json
import os
import sqlite3
import sys
from typing import Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import db
from profile_columns import build_profile_columns


def table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def column_exists(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return any(row["name"] == column_name for row in cursor.fetchall())


def first_existing_table(cursor: sqlite3.Cursor, names: tuple[str, ...]) -> str | None:
    for name in names:
        if table_exists(cursor, name):
            return name
    return None


def select_expr(cursor: sqlite3.Cursor, table_name: str, column_name: str, fallback_sql: str) -> str:
    return f"{table_name}.{column_name}" if column_exists(cursor, table_name, column_name) else fallback_sql


def row_value(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    return row[key] if key in row.keys() else default


def active_profile_id(cursor: sqlite3.Cursor, job_posting_id: int) -> int | None:
    cursor.execute(
        """
        SELECT id
        FROM job_profiles
        WHERE job_posting_id = ?
          AND is_active = 1
        """,
        (job_posting_id,),
    )
    row = cursor.fetchone()
    return row["id"] if row else None


def upsert_job_profile(cursor: sqlite3.Cursor, columns: dict[str, Any]) -> None:
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
            columns["job_posting_id"],
            columns["content_hash"],
            columns["schema_version"],
            columns["prompt_version"],
            columns["model_version"],
        ),
    )

    column_sql = ", ".join(db.PROFILE_COLUMNS)
    placeholders = ", ".join(["?"] * len(db.PROFILE_COLUMNS))
    update_columns = ", ".join([f"{column} = excluded.{column}" for column in db.PROFILE_UPDATE_COLUMNS])
    cursor.execute(
        f"""
        INSERT INTO job_profiles ({column_sql})
        VALUES ({placeholders})
        ON CONFLICT(job_posting_id, content_hash, schema_version, prompt_version, model_version)
        DO UPDATE SET {update_columns},
                      invalidated_at = NULL,
                      invalidated_reason = NULL
        """,
        [columns[column] for column in db.PROFILE_COLUMNS],
    )


def backfill_legacy_job_tables() -> dict[str, int]:
    conn = db.get_db_connection()
    db.apply_schema_migrations(conn)
    cursor = conn.cursor()

    jobs_table = first_existing_table(cursor, ("jobs_deprecated", "jobs"))
    job_content_table = first_existing_table(cursor, ("job_content_deprecated", "job_content"))
    match_results_table = first_existing_table(
        cursor,
        ("legacy_match_results_deprecated", "legacy_match_results", "match_results_deprecated"),
    )
    user_actions_table = first_existing_table(
        cursor,
        ("legacy_user_actions_deprecated", "legacy_user_actions", "user_actions_deprecated"),
    )

    if not jobs_table or not job_content_table:
        cursor.close()
        conn.close()
        return {
            "postings_backfilled": 0,
            "profiles_backfilled": 0,
            "match_results_backfilled": 0,
            "user_actions_backfilled": 0,
        }

    cursor.execute(
        f"""
        SELECT
            {jobs_table}.*,
            {job_content_table}.raw_text,
            {select_expr(cursor, job_content_table, "profile_json", "NULL AS profile_json")},
            {select_expr(cursor, job_content_table, "extraction_status", "NULL AS extraction_status")},
            {select_expr(cursor, job_content_table, "extraction_error", "NULL AS extraction_error")},
            {select_expr(cursor, job_content_table, "extracted_at", "NULL AS extracted_at")}
        FROM {jobs_table}
        JOIN {job_content_table}
          ON {job_content_table}.job_id = {jobs_table}.id
        """
    )
    legacy_rows = cursor.fetchall()

    postings_backfilled = 0
    profiles_backfilled = 0

    for row in legacy_rows:
        title_raw = row_value(row, "title")
        location_raw = row_value(row, "location")
        cleaned_text = row["raw_text"]
        source_posting_id = str(row_value(row, "source_id", row["id"]))
        content_hash = db.compute_content_hash(title_raw, location_raw, cleaned_text)

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
                source_metadata_json,
                cleaned_description_text,
                raw_description_text,
                content_hash,
                first_seen_at,
                last_seen_at,
                imported_at,
                updated_at,
                last_content_changed_at,
                profile_status,
                last_profile_attempt_at,
                last_profile_error,
                is_deleted_at_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, 0)
            ON CONFLICT(source_system, source_posting_id) DO UPDATE SET
                source_url = excluded.source_url,
                title_raw = excluded.title_raw,
                company_raw = excluded.company_raw,
                location_raw = excluded.location_raw,
                posted_date_raw = excluded.posted_date_raw,
                source_file = excluded.source_file,
                source_metadata_json = excluded.source_metadata_json,
                cleaned_description_text = excluded.cleaned_description_text,
                raw_description_text = excluded.raw_description_text,
                content_hash = excluded.content_hash,
                updated_at = CURRENT_TIMESTAMP,
                profile_status = excluded.profile_status,
                last_profile_attempt_at = excluded.last_profile_attempt_at,
                last_profile_error = excluded.last_profile_error
            """,
            (
                "linkedin",
                source_posting_id,
                row_value(row, "url"),
                title_raw,
                row_value(row, "company"),
                location_raw,
                row_value(row, "posted_date"),
                row_value(row, "source_file"),
                json.dumps({"legacy_job_id": row["id"]}, sort_keys=True),
                cleaned_text,
                cleaned_text,
                content_hash,
                "current" if row["profile_json"] else (row["extraction_status"] or "missing"),
                row["extracted_at"],
                row["extraction_error"],
            ),
        )

        cursor.execute(
            """
            SELECT id
            FROM job_postings
            WHERE source_system = 'linkedin'
              AND source_posting_id = ?
            """,
            (source_posting_id,),
        )
        posting_id = cursor.fetchone()["id"]
        postings_backfilled += 1

        if row["profile_json"] and content_hash:
            profile_payload = json.loads(row["profile_json"])
            profile_columns = build_profile_columns(
                profile_payload,
                job_posting_id=posting_id,
                content_hash=content_hash,
                extracted_at=row["extracted_at"],
            )
            upsert_job_profile(cursor, profile_columns)
            profiles_backfilled += 1

    match_results_backfilled = backfill_match_results(cursor, match_results_table, jobs_table) if match_results_table else 0
    user_actions_backfilled = backfill_user_actions(cursor, user_actions_table, jobs_table) if user_actions_table else 0

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "postings_backfilled": postings_backfilled,
        "profiles_backfilled": profiles_backfilled,
        "match_results_backfilled": match_results_backfilled,
        "user_actions_backfilled": user_actions_backfilled,
    }


def backfill_match_results(cursor: sqlite3.Cursor, table_name: str, jobs_table: str) -> int:
    if not column_exists(cursor, table_name, "job_id"):
        return 0

    has_reasoning = column_exists(cursor, table_name, "reasoning")
    cursor.execute(
        f"""
        SELECT mr.*, j.source_id
        FROM {table_name} mr
        JOIN {jobs_table} j ON j.id = mr.job_id
        """
    )

    count = 0
    for row in cursor.fetchall():
        cursor.execute(
            """
            SELECT id
            FROM job_postings
            WHERE source_system = 'linkedin'
              AND source_posting_id = ?
            """,
            (row["source_id"],),
        )
        posting = cursor.fetchone()
        if posting is None:
            continue

        stage1_reasoning = row["reasoning"] if has_reasoning and row["stage2_decision"] is None else None
        stage2_reasoning = row["reasoning"] if has_reasoning and row["stage2_decision"] is not None else None

        cursor.execute(
            """
            INSERT INTO match_results (
                job_posting_id,
                job_profile_id,
                stage1_score,
                stage1_decision,
                stage1_reasoning,
                stage2_score,
                stage2_decision,
                stage2_reasoning
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_posting_id) DO UPDATE SET
                job_profile_id = excluded.job_profile_id,
                stage1_score = excluded.stage1_score,
                stage1_decision = excluded.stage1_decision,
                stage1_reasoning = excluded.stage1_reasoning,
                stage2_score = excluded.stage2_score,
                stage2_decision = excluded.stage2_decision,
                stage2_reasoning = excluded.stage2_reasoning
            """,
            (
                posting["id"],
                active_profile_id(cursor, posting["id"]),
                row["stage1_score"],
                row["stage1_decision"],
                stage1_reasoning,
                row["stage2_score"],
                row["stage2_decision"],
                stage2_reasoning,
            ),
        )
        count += 1

    return count


def backfill_user_actions(cursor: sqlite3.Cursor, table_name: str, jobs_table: str) -> int:
    if not column_exists(cursor, table_name, "job_id"):
        return 0

    cursor.execute(
        f"""
        SELECT ua.*, j.source_id
        FROM {table_name} ua
        JOIN {jobs_table} j ON j.id = ua.job_id
        """
    )

    count = 0
    for row in cursor.fetchall():
        cursor.execute(
            """
            SELECT id
            FROM job_postings
            WHERE source_system = 'linkedin'
              AND source_posting_id = ?
            """,
            (row["source_id"],),
        )
        posting = cursor.fetchone()
        if posting is None:
            continue

        cursor.execute(
            """
            INSERT INTO user_actions (job_posting_id, status, notes, updated_at)
            SELECT ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP)
            WHERE NOT EXISTS (
                SELECT 1
                FROM user_actions
                WHERE job_posting_id = ?
                  AND COALESCE(status, '') = COALESCE(?, '')
                  AND COALESCE(notes, '') = COALESCE(?, '')
            )
            """,
            (
                posting["id"],
                row_value(row, "status"),
                row_value(row, "notes"),
                row_value(row, "updated_at"),
                posting["id"],
                row_value(row, "status"),
                row_value(row, "notes"),
            ),
        )
        count += cursor.rowcount

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill new job_postings/job_profiles tables from legacy job tables.")
    parser.parse_args()

    summary = backfill_legacy_job_tables()
    print("Legacy job-table backfill completed.")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
