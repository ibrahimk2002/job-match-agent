import sqlite3
import os
import logging
import json

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_LOG_PATH = os.path.join(_PROJECT_ROOT, 'logs', 'job_matcher.log')
_DB_PATH = os.path.join(_PROJECT_ROOT, 'data', 'job_matcher.db')

os.makedirs(os.path.join(_PROJECT_ROOT, 'logs'), exist_ok=True)
os.makedirs(os.path.join(_PROJECT_ROOT, 'data'), exist_ok=True)

logging.basicConfig(filename=_LOG_PATH, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_db_connection():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Source metadata — one row per job posting as ingested from cleaned report artifacts
    cursor.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id   TEXT NOT NULL UNIQUE,
        url         TEXT,
        title       TEXT,
        company     TEXT,
        location    TEXT,
        posted_date TEXT,
        source_file TEXT,
        imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # Extraction pipeline state + canonical JobProfile content
    # profile_json holds the full validated JobProfile object (model_dump_json).
    # Promoted columns are derived conveniences only; profile_json is the source of truth.
    cursor.execute('''CREATE TABLE IF NOT EXISTS job_content (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id                INTEGER NOT NULL UNIQUE,
        raw_text              TEXT,
        extraction_status     TEXT NOT NULL DEFAULT 'pending',
        extraction_error      TEXT,
        extracted_at          DATETIME,
        profile_json          TEXT,
        role_family           TEXT,
        seniority             TEXT,
        work_mode             TEXT,
        extraction_confidence REAL,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )''')

    # Two-stage match scoring; reasoning stored separately per stage
    cursor.execute('''CREATE TABLE IF NOT EXISTS match_results (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id           INTEGER NOT NULL UNIQUE,
        stage1_score     REAL,
        stage1_decision  TEXT,
        stage1_reasoning TEXT,
        stage2_score     REAL,
        stage2_decision  TEXT,
        stage2_reasoning TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )''')

    # Human tracking of job application status
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_actions (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id     INTEGER NOT NULL,
        status     TEXT,
        notes      TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )''')

    conn.commit()
    cursor.close()
    conn.close()

# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

def import_jobs_from_jsonl(jsonl_path: str) -> int:
    """Insert jobs from a cleaned LinkedIn JSONL file. Returns count of new rows inserted."""
    source_file = os.path.basename(jsonl_path)
    inserted = 0
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                source_id = str(row.get('job_id', '')).strip()
                if not source_id:
                    continue
                cursor.execute("""
                    INSERT OR IGNORE INTO jobs (source_id, url, title, company, location, posted_date, source_file)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    source_id,
                    str(row.get('url', '')).strip() or None,
                    str(row.get('title', '')).strip() or None,
                    str(row.get('company', '')).strip() or None,
                    str(row.get('location', '')).strip() or None,
                    str(row.get('posted_date', '')).strip() or None,
                    row.get('meta_source_file') or source_file,
                ))
                job_id = cursor.lastrowid
                if cursor.rowcount > 0 and job_id:
                    raw_text = str(row.get('description', '')).strip() or None
                    cursor.execute("""
                        INSERT OR IGNORE INTO job_content (job_id, raw_text, extraction_status)
                        VALUES (?, ?, 'pending')
                    """, (job_id, raw_text))
                    inserted += 1
        conn.commit()
        logging.info(f"Imported {inserted} new jobs from {source_file}")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error importing {jsonl_path}: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
    return inserted

# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def get_pending_extraction():
    """Return job_content rows that have not yet been extracted."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT jc.job_id, j.source_id, jc.raw_text
        FROM job_content jc
        JOIN jobs j ON j.id = jc.job_id
        WHERE jc.extraction_status = 'pending' AND jc.raw_text IS NOT NULL
    """)
    results = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return results

def save_extraction(job_id: int, profile) -> None:
    """
    Persist a validated JobProfile object.
    profile must be a JobProfile Pydantic model instance.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE job_content
        SET profile_json          = ?,
            extraction_status     = 'done',
            extraction_error      = NULL,
            extracted_at          = CURRENT_TIMESTAMP,
            role_family           = ?,
            seniority             = ?,
            work_mode             = ?,
            extraction_confidence = ?
        WHERE job_id = ?
    """, (
        profile.model_dump_json(),
        profile.role_family,
        profile.seniority,
        profile.work_mode,
        profile.extraction_confidence,
        job_id,
    ))
    conn.commit()
    cursor.close()
    conn.close()
    logging.info(f"Saved extraction for job_id: {job_id}")

def fail_extraction(job_id: int, error: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE job_content
        SET extraction_status = 'failed',
            extraction_error  = ?
        WHERE job_id = ?
    """, (error, job_id))
    conn.commit()
    cursor.close()
    conn.close()
    logging.warning(f"Extraction failed for job_id {job_id}: {error}")

# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def get_jobs_for_stage1():
    """Jobs with a completed extraction that have not entered matching yet."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT j.id, j.source_id, j.title, j.company, jc.profile_json
        FROM jobs j
        JOIN job_content jc ON j.id = jc.job_id
        LEFT JOIN match_results mr ON j.id = mr.job_id
        WHERE jc.extraction_status = 'done'
          AND mr.id IS NULL
    """)
    results = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return results

def save_stage1_result(job_id: int, score: float, decision: str, reasoning: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO match_results (job_id, stage1_score, stage1_decision, stage1_reasoning)
        VALUES (?, ?, ?, ?)
    """, (job_id, score, decision, reasoning))
    conn.commit()
    cursor.close()
    conn.close()
    logging.info(f"Stage1 result for job_id {job_id}: {decision} ({score})")

def get_jobs_for_stage2():
    """Jobs that passed stage 1 and have not yet been scored in stage 2."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT j.id, j.source_id, j.title, j.company, jc.profile_json, mr.stage1_score
        FROM jobs j
        JOIN job_content jc ON j.id = jc.job_id
        JOIN match_results mr ON j.id = mr.job_id
        WHERE mr.stage1_decision = 'advance'
          AND mr.stage2_score IS NULL
    """)
    results = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return results

def save_stage2_result(job_id: int, score: float, decision: str, reasoning: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE match_results
        SET stage2_score    = ?,
            stage2_decision = ?,
            stage2_reasoning = ?
        WHERE job_id = ?
    """, (score, decision, reasoning, job_id))
    conn.commit()
    cursor.close()
    conn.close()
    logging.info(f"Stage2 result for job_id {job_id}: {decision} ({score})")

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

def get_top_matches(limit: int = 10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT j.title, j.company, j.url,
               mr.stage2_score    AS score,
               mr.stage2_decision AS decision,
               mr.stage2_reasoning AS reasoning
        FROM jobs j
        JOIN match_results mr ON j.id = mr.job_id
        WHERE mr.stage2_decision IS NOT NULL
        ORDER BY mr.stage2_score DESC
        LIMIT ?
    """, (limit,))
    results = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return results
