import json
import os
from integrations.openai_client import call_llm
from db import insert_match_result, get_jobs_for_stage2
from utils.utils import log_info

def run_stage2_matching(profile):
    jobs = get_jobs_for_stage2()
    prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'match2.txt')
    with open(prompt_path, 'r') as f:
        prompt_template = f.read()
    for job in jobs:
        job_data = json.loads(job['extraction_json']) if job['extraction_json'] else {}
        prompt = prompt_template.format(profile=json.dumps(profile), job=json.dumps(job_data))
        result = call_llm(prompt)
        insert_match_result(job['id'], job['stage1_score'], 'advance', result['score'], result['decision'], reasoning=result.get('reasoning'))
        log_info(f"Stage2 match for job {job['id']}: {result['decision']}")
