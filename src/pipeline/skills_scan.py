import os
from utils import log_info
from integrations.openai_client import scan_job_skills, scan_resume_skills
from skills import batch_canonicalize
from db import save_job_profile_skills, save_resume_skills

DEFAULT_MODEL = "gpt-4.1-nano"

_JOB_PROMPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'skills_scan.txt')
_RESUME_PROMPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'resume_skills_scan.txt')

_IMPORTANCE_RANK = {"must": 3, "preferred": 2, "nice": 1}


def _read_prompt(path: str) -> tuple[str, str]:
    with open(path, 'r') as f:
        content = f.read()
    first_line = content.splitlines()[0].strip() if content else ""
    version = first_line.split(":", 1)[1].strip() if first_line.startswith("# prompt_version:") else "unknown"
    return content, version


_JOB_SYSTEM_PROMPT, _JOB_SKILLS_PROMPT_VERSION = _read_prompt(_JOB_PROMPT_PATH)
_RESUME_SYSTEM_PROMPT, _RESUME_SKILLS_PROMPT_VERSION = _read_prompt(_RESUME_PROMPT_PATH)
_JOB_CACHE_KEY = f"skills_scan_job:{_JOB_SKILLS_PROMPT_VERSION}:{DEFAULT_MODEL}"
_RESUME_CACHE_KEY = f"skills_scan_resume:{_RESUME_SKILLS_PROMPT_VERSION}:{DEFAULT_MODEL}"


def _dedup_job_entries(
    entries: list[tuple[int, str, int | None]],
) -> list[tuple[int, str, int | None]]:
    """Deduplicate by skill_id; when the same id appears twice, keep highest importance."""
    best: dict[int, tuple[str, int | None]] = {}
    for skill_id, importance, group_id in entries:
        if skill_id not in best or _IMPORTANCE_RANK[importance] > _IMPORTANCE_RANK[best[skill_id][0]]:
            best[skill_id] = (importance, group_id)
    return [(sid, imp, gid) for sid, (imp, gid) in best.items()]


def _dedup_resume_entries(
    entries: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    """Deduplicate by skill_id; keep highest importance on collision."""
    best: dict[int, str] = {}
    for skill_id, importance in entries:
        if skill_id not in best or _IMPORTANCE_RANK[importance] > _IMPORTANCE_RANK[best[skill_id]]:
            best[skill_id] = importance
    return [(sid, imp) for sid, imp in best.items()]


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
            system_prompt=_JOB_SYSTEM_PROMPT,
            model=DEFAULT_MODEL,
            prompt_cache_key=_JOB_CACHE_KEY,
        )
    except Exception as e:
        log_info(f"skills_scan: job_profile_id={job_profile_id} scan failed (non-fatal): {e}")
        return

    valid = [e for e in result.skills if e.skill.strip()]
    if not valid:
        log_info(f"skills_scan: job_profile_id={job_profile_id} LLM returned no skills")
        return

    skill_ids = batch_canonicalize([e.skill for e in valid], conn)
    entries = _dedup_job_entries([
        (sid, e.importance, e.group_id) for sid, e in zip(skill_ids, valid)
    ])
    save_job_profile_skills(job_profile_id, entries, conn)
    conn.commit()
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
            system_prompt=_RESUME_SYSTEM_PROMPT,
            model=DEFAULT_MODEL,
            prompt_cache_key=_RESUME_CACHE_KEY,
        )
    except Exception as e:
        log_info(f"skills_scan: user_profile_id={user_profile_id} resume scan failed (non-fatal): {e}")
        return

    valid = [e for e in result.skills if e.skill.strip()]
    if not valid:
        log_info(f"skills_scan: user_profile_id={user_profile_id} LLM returned no skills")
        return

    skill_ids = batch_canonicalize([e.skill for e in valid], conn)
    entries = _dedup_resume_entries([
        (sid, e.importance) for sid, e in zip(skill_ids, valid)
    ])
    save_resume_skills(user_profile_id, entries, conn)
    conn.commit()
    log_info(f"skills_scan: user_profile_id={user_profile_id} saved {len(entries)} resume skills")
