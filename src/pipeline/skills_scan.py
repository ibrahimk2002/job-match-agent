import os
from utils import log_info
from integrations.openai_client import scan_job_skills, scan_resume_skills, MalformedOutputError
from skills import batch_canonicalize
from db import save_job_profile_skills, save_resume_skills

DEFAULT_MODEL = "gpt-4.1-nano"

_JOB_PROMPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'skills_scan.txt')
_RESUME_PROMPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'resume_skills_scan.txt')


def _read_prompt_version(path: str) -> str:
    with open(path, 'r') as f:
        first_line = f.readline().strip()
    if first_line.startswith("# prompt_version:"):
        return first_line.split(":", 1)[1].strip()
    return "unknown"


_JOB_SKILLS_PROMPT_VERSION = _read_prompt_version(_JOB_PROMPT_PATH)
_RESUME_SKILLS_PROMPT_VERSION = _read_prompt_version(_RESUME_PROMPT_PATH)
_JOB_CACHE_KEY = f"skills_scan_job:{_JOB_SKILLS_PROMPT_VERSION}:{DEFAULT_MODEL}"
_RESUME_CACHE_KEY = f"skills_scan_resume:{_RESUME_SKILLS_PROMPT_VERSION}:{DEFAULT_MODEL}"


def populate_job_skills(
    job_profile_id: int,
    job_text: str,
    profile_json: str,
    conn,
) -> None:
    try:
        result, _ = scan_job_skills(
            job_text,
            profile_json,
            model=DEFAULT_MODEL,
            prompt_cache_key=_JOB_CACHE_KEY,
        )
    except Exception as e:
        log_info(f"skills_scan: job_profile_id={job_profile_id} scan failed (non-fatal): {e}")
        return

    raw_skills = [entry.skill for entry in result.skills]
    skill_ids = batch_canonicalize(raw_skills, conn)

    entries = [
        (skill_id, entry.importance, entry.group_id)
        for skill_id, entry in zip(skill_ids, result.skills)
    ]
    save_job_profile_skills(job_profile_id, entries, conn)
    log_info(f"skills_scan: job_profile_id={job_profile_id} saved {len(entries)} job skills")


def populate_resume_skills(
    user_profile_id: int,
    resume_text: str,
    profile_json: str,
    conn,
) -> None:
    try:
        result, _ = scan_resume_skills(
            resume_text,
            profile_json,
            model=DEFAULT_MODEL,
            prompt_cache_key=_RESUME_CACHE_KEY,
        )
    except Exception as e:
        log_info(f"skills_scan: user_profile_id={user_profile_id} resume scan failed (non-fatal): {e}")
        return

    raw_skills = [entry.skill for entry in result.skills]
    skill_ids = batch_canonicalize(raw_skills, conn)

    entries = [
        (skill_id, entry.importance)
        for skill_id, entry in zip(skill_ids, result.skills)
    ]
    save_resume_skills(user_profile_id, entries, conn)
    log_info(f"skills_scan: user_profile_id={user_profile_id} saved {len(entries)} resume skills")
