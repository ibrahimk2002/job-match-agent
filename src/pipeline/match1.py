import json
import os
from integrations.openai_client import call_llm
from db import insert_match_result
from utils.utils import log_info

def run_stage1_matching(profile):
    from db import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT j.*, jc.extraction_json
        FROM jobs j
        JOIN job_content jc ON j.id = jc.job_id
        LEFT JOIN match_results mr ON j.id = mr.job_id
        WHERE mr.id IS NULL
    """)
    jobs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'match1.txt')
    with open(prompt_path, 'r') as f:
        prompt_template = f.read()
    for job in jobs:
        job_data = json.loads(job['extraction_json']) if job['extraction_json'] else {}
        prompt = prompt_template.format(profile=json.dumps(profile), job=json.dumps(job_data))
        result = call_llm(prompt)
        insert_match_result(job['id'], result['score'], result['decision'], reasoning=result.get('reasoning'))
        log_info(f"Stage1 match for job {job['id']}: {result['decision']}")
