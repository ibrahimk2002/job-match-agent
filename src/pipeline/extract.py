import os
import sys
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.job_profile import JobProfile, ProfileMeta
from integrations import extract_job_profile
from db import get_pending_extraction, save_extraction, fail_extraction
from utils import log_info


DEFAULT_MODEL = "gpt-4.1-nano"
SCHEMA_VERSION = "1.0"


def _read_prompt_and_version(prompt_path: str) -> tuple[str, str]:
    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    first_line = content.splitlines()[0].strip() if content else ""
    if first_line.startswith("# prompt_version:"):
        return content, first_line.split(":", 1)[1].strip()
    return content, "unknown"


def extract_job_data():
    prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'extraction.txt')
    system_prompt, prompt_version = _read_prompt_and_version(prompt_path)
    pending = get_pending_extraction(
        schema_version=SCHEMA_VERSION,
        prompt_version=prompt_version,
        model_version=DEFAULT_MODEL,
    )

    for job in pending:
        db_job_id = job['job_posting_id']
        source_id = job['source_id']
        print(f"Processing job_id {db_job_id} with source_id {source_id}")
        try:
            extraction_result = extract_job_profile(
                system_prompt=system_prompt,
                job_text=job['raw_text'],
                model=DEFAULT_MODEL,
            )
            profile_meta = ProfileMeta(
                schema_version=SCHEMA_VERSION,
                prompt_version=prompt_version,
                model=DEFAULT_MODEL,
                generated_at=datetime.now(timezone.utc).isoformat(),
            )
            profile = JobProfile(
                job_id=source_id,
                profile_meta=profile_meta,
                **extraction_result.model_dump(),
            )
            save_extraction(db_job_id, profile)
            log_info(f"Extracted data for job_id {db_job_id}: {profile.role_family} / {profile.seniority}")
        except Exception as e:
            fail_extraction(db_job_id, str(e))
            log_info(f"Extraction failed for job_id {db_job_id}: {e}")
