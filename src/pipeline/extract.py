import os
import sys
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from pydantic import ValidationError

from config.job_profile import JobProfile, ProfileMeta
from integrations import extract_job_profile, MalformedOutputError
from db import get_pending_extraction, save_extraction, fail_extraction
from utils import log_info


DEFAULT_MODEL = "gpt-4.1-nano"
SCHEMA_VERSION = "2.0"
_MAX_INPUT_CHARS = 60_000  # ~15k tokens; well under nano's window


def _read_prompt_and_version(prompt_path: str) -> tuple[str, str]:
    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    first_line = content.splitlines()[0].strip() if content else ""
    if first_line.startswith("# prompt_version:"):
        return content, first_line.split(":", 1)[1].strip()
    return content, "unknown"


_PROMPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'extraction.txt')
_SYSTEM_PROMPT, _PROMPT_VERSION = _read_prompt_and_version(_PROMPT_PATH)
_PROMPT_CACHE_KEY = f"extract:{SCHEMA_VERSION}:{_PROMPT_VERSION}:{DEFAULT_MODEL}"


def _attempt_extraction(job_text: str):
    """One call to the LLM. Returns (parsed, usage) or raises."""
    return extract_job_profile(
        system_prompt=_SYSTEM_PROMPT,
        job_text=job_text,
        model=DEFAULT_MODEL,
        prompt_cache_key=_PROMPT_CACHE_KEY,
    )


def extract_job_data():
    pending = get_pending_extraction(
        schema_version=SCHEMA_VERSION,
        prompt_version=_PROMPT_VERSION,
        model_version=DEFAULT_MODEL,
    )

    for job in pending:
        _process_one(job)


def _process_one(job: dict) -> None:
    db_job_id = job['job_posting_id']
    source_id = job['source_id']
    raw_text = job.get('raw_text')

    if not raw_text or not raw_text.strip():
        fail_extraction(db_job_id, "missing_description")
        log_info(f"Extraction skipped for job_id {db_job_id}: missing_description")
        return

    job_text = raw_text
    if len(job_text) > _MAX_INPUT_CHARS:
        log_info(
            f"Extraction truncating job_id {db_job_id}: "
            f"{len(job_text)} chars -> {_MAX_INPUT_CHARS}"
        )
        job_text = job_text[:_MAX_INPUT_CHARS]

    print(f"Processing job_id {db_job_id} with source_id {source_id}")

    extraction_result = None
    last_err: Exception | None = None
    last_kind: str | None = None
    for attempt in (1, 2):
        try:
            extraction_result, _usage = _attempt_extraction(job_text)
            break
        except (MalformedOutputError, ValidationError) as e:
            last_err = e
            last_kind = "malformed_output"
            log_info(
                f"Extraction attempt {attempt} ({last_kind}) for job_id {db_job_id}: {e}"
            )
        except Exception as e:
            last_err = e
            last_kind = "api_error"
            log_info(
                f"Extraction attempt {attempt} ({last_kind}) for job_id {db_job_id}: {e}"
            )

    if extraction_result is None:
        err_msg = f"{last_kind}: {last_err}"
        fail_extraction(db_job_id, err_msg)
        log_info(f"Extraction failed for job_id {db_job_id} after retry: {err_msg}")
        return

    profile_meta = ProfileMeta(
        schema_version=SCHEMA_VERSION,
        prompt_version=_PROMPT_VERSION,
        model=DEFAULT_MODEL,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    profile = JobProfile(
        job_id=source_id,
        profile_meta=profile_meta,
        **extraction_result.model_dump(),
    )
    save_extraction(db_job_id, profile)
    log_info(
        f"Extracted data for job_id {db_job_id}: "
        f"{profile.role_family} / {profile.seniority}"
    )
