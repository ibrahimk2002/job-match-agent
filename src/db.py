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
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT NOT NULL,
        url_hash TEXT NOT NULL UNIQUE,
        company TEXT,
        title TEXT,
        location TEXT,
        first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS job_content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        raw_text TEXT,
        extraction_json TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS match_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        stage1_score REAL,
        stage1_decision TEXT,
        stage2_score REAL,
        stage2_decision TEXT,
        reasoning TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS user_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        status TEXT,
        notes TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )''')
    conn.commit()
    cursor.close()
    conn.close()

def insert_job(url, url_hash, company=None, title=None, location=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO jobs (url, url_hash, company, title, location, last_seen)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (url, url_hash, company, title, location))
        job_id = cursor.lastrowid
        conn.commit()
        logging.info(f"Inserted/updated job: {url}")
        return job_id
    except Exception as e:
        logging.error(f"Error inserting job {url}: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def update_job_content(job_id, raw_text, extraction_json):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO job_content (job_id, raw_text, extraction_json)
        VALUES (?, ?, ?)
    """, (job_id, raw_text, extraction_json))
    conn.commit()
    cursor.close()
    conn.close()
    logging.info(f"Updated job content for job_id: {job_id}")

def insert_match_result(job_id, stage1_score, stage1_decision, stage2_score=None, stage2_decision=None, reasoning=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO match_results (job_id, stage1_score, stage1_decision, stage2_score, stage2_decision, reasoning)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (job_id, stage1_score, stage1_decision, stage2_score, stage2_decision, json.dumps(reasoning) if reasoning else None))
    conn.commit()
    cursor.close()
    conn.close()
    logging.info(f"Inserted match result for job_id: {job_id}")

def get_jobs_for_stage2():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT j.*, jc.extraction_json, mr.stage1_score
        FROM jobs j
        JOIN job_content jc ON j.id = jc.job_id
        JOIN match_results mr ON j.id = mr.job_id
        WHERE mr.stage1_decision = 'advance' AND mr.stage2_score IS NULL
    """)
    results = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return results

def get_top_matches(limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT j.title, j.company, mr.stage2_score as score, mr.stage2_decision as decision
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
