import json
import os
from integrations.openai_client import call_llm
from db import update_job_content
from utils.utils import log_info

def extract_job_data():
    from db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM job_content WHERE extraction_json IS NULL AND raw_text IS NOT NULL")
    pending = cursor.fetchall()
    conn.close()
    prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'extraction.txt')
    with open(prompt_path, 'r') as f:
        prompt_template = f.read()
    for job in pending:
        prompt = prompt_template.format(raw_text=job[2])
        result = call_llm(prompt)
        update_job_content(job[1], job[2], json.dumps(result))
        log_info(f"Extracted data for job {job[1]}")
