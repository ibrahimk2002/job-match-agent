from integrations.firecrawl import scrape_job
from db import get_pending_jobs, update_job_content

def scrape_pending_jobs():
    pending = get_pending_jobs()
    for job in pending:
        try:
            raw_text = scrape_job(job['url'])
            update_job_content(job['job_id'], raw_text, None, 'success')
        except Exception as e:
            update_job_content(job['job_id'], None, None, 'failed', str(e))
