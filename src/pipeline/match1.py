import json
import os
from integrations.openai_client import call_llm
from db import get_jobs_for_stage1, save_stage1_result
from utils.utils import log_info

def run_stage1_matching(profile):
    jobs = get_jobs_for_stage1()
    prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'match1.txt')
    with open(prompt_path, 'r') as f:
        prompt_template = f.read()
    for job in jobs:
        job_data = json.loads(job['profile_json']) if job['profile_json'] else {}
        prompt = prompt_template.format(profile=json.dumps(profile), job=json.dumps(job_data))
        result = call_llm(prompt)
        save_stage1_result(
            job['id'],
            result['score'],
            result['decision'],
            result.get('reasoning', ''),
        )
        log_info(f"Stage1 match for job {job['id']}: {result['decision']}")
