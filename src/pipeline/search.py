from integrations.firecrawl import search_jobs
from db import insert_job, update_job_content
from utils.utils import hash_url

def search_and_insert_jobs(query):
    jobs = search_jobs(query)
    for job in jobs:
        url_hash = hash_url(job['url'])
        job_id = insert_job(job['url'], url_hash, job.get('company'), job.get('title'), job.get('location'))
        # Insert job_content with pending
        update_job_content(job_id, None, None, 'pending')
    return len(jobs)
