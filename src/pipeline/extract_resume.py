import hashlib
import os
import sys
from datetime import datetime, timezone

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_SRC = os.path.join(_PROJECT_ROOT, 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from pydantic import ValidationError

from config.job_profile import ProfileMeta
from config.user_profile import UserProfile
from db import get_or_create_user, get_active_user_profile, save_resume_extraction
from integrations import extract_resume_profile, MalformedOutputError
from user_profile_columns import build_profile_columns
from utils import log_info


SCHEMA_VERSION = "1.0"
DEFAULT_MODEL = "gpt-4.1-nano"
_MAX_INPUT_CHARS = 60_000


def _read_prompt_and_version(prompt_path: str) -> tuple[str, str]:
    with open(prompt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    first_line = content.splitlines()[0].strip() if content else ""
    if first_line.startswith("# prompt_version:"):
        return content, first_line.split(":", 1)[1].strip()
    return content, "unknown"


_PROMPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'resume_extraction.txt')
_SYSTEM_PROMPT, _PROMPT_VERSION = _read_prompt_and_version(_PROMPT_PATH)
_PROMPT_CACHE_KEY = f"resume:{SCHEMA_VERSION}:{_PROMPT_VERSION}:{DEFAULT_MODEL}"


def _extract_pdf_text(pdf_path: str) -> str:
    import pypdf
    reader = pypdf.PdfReader(pdf_path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _is_current(active: dict, content_hash: str) -> bool:
    return (
        active["content_hash"] == content_hash
        and active["schema_version"] == SCHEMA_VERSION
        and active["prompt_version"] == _PROMPT_VERSION
        and active["model_version"] == DEFAULT_MODEL
    )


def _attempt_extraction(resume_text: str):
    return extract_resume_profile(
        system_prompt=_SYSTEM_PROMPT,
        resume_text=resume_text,
        model=DEFAULT_MODEL,
        prompt_cache_key=_PROMPT_CACHE_KEY,
    )


def _log_usage(user_id: int, usage) -> None:
    if usage is None:
        return
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    details = getattr(usage, "input_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) if details is not None else 0
    pct = 100.0 * cached / input_tokens if input_tokens > 0 else 0.0
    log_info(
        f"resume: user_id={user_id} model={DEFAULT_MODEL} "
        f"input={input_tokens} cached={cached} ({pct:.1f}%)"
    )


def _run_extraction_and_save(user_id: int, resume_text: str, content_hash: str) -> UserProfile:
    extraction_result = None
    usage = None
    last_err: Exception | None = None
    last_kind: str | None = None
    for attempt in (1, 2):
        try:
            extraction_result, usage = _attempt_extraction(resume_text)
            break
        except (MalformedOutputError, ValidationError) as e:
            last_err = e
            last_kind = "malformed_output"
            log_info(f"resume: attempt {attempt} ({last_kind}): {e}")
        except Exception as e:
            last_err = e
            last_kind = "api_error"
            log_info(f"resume: attempt {attempt} ({last_kind}): {e}")

    if extraction_result is None:
        raise RuntimeError(f"Resume extraction failed: {last_kind}: {last_err}")

    profile = UserProfile(
        meta=ProfileMeta(
            schema_version=SCHEMA_VERSION,
            prompt_version=_PROMPT_VERSION,
            model=DEFAULT_MODEL,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        **extraction_result.model_dump(),
    )

    columns = build_profile_columns(profile)
    save_resume_extraction(user_id, profile, columns, content_hash=content_hash)
    _log_usage(user_id, usage)
    return profile


def extract_resume(pdf_path: str, email: str) -> None:
    raw_text = _extract_pdf_text(pdf_path)
    if not raw_text.strip():
        raise ValueError("no extractable text — scanned or image-only PDF")

    if len(raw_text) > _MAX_INPUT_CHARS:
        log_info(f"resume: truncating {len(raw_text)} chars to {_MAX_INPUT_CHARS}")
    resume_text = raw_text[:_MAX_INPUT_CHARS]

    content_hash = hashlib.sha256(raw_text.encode()).hexdigest()
    user_id = get_or_create_user(email)

    active = get_active_user_profile(user_id)
    if active and _is_current(active, content_hash):
        log_info(f"resume: user_id={user_id} already up to date, skipping")
        print("Profile is already up to date.")
        return

    profile = _run_extraction_and_save(user_id, resume_text, content_hash)

    if profile.extraction_confidence < 0.5:
        print(f"Warning: low extraction confidence ({profile.extraction_confidence:.2f}) — review profile")

    print(
        f"Extracted: {profile.full_name or 'Unknown'} | "
        f"{profile.current_level} {profile.primary_role_family} | "
        f"confidence={profile.extraction_confidence:.2f}"
    )
