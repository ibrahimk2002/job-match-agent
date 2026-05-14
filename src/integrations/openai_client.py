import json

import dotenv
dotenv.load_dotenv()
from openai import OpenAI
from utils import config

from models.job_profile import JobProfile, ExtractionResult


class MalformedOutputError(RuntimeError):
    """Raised when the LLM's response cannot be parsed into ExtractionResult.

    Distinguishes 'the model returned bad output' from 'the API call failed'
    so the extraction loop can apply the right error label.
    """
    pass


def get_openai_client() -> OpenAI:
    return OpenAI(api_key=config.OPENAI_API_KEY)


def call_llm(prompt: str):
    client = get_openai_client()

    try:
        response = client.responses.create(model="gpt-4.1-nano", input=prompt)
        content = response.output_text
        if not content:
            raise ValueError("LLM returned empty content")
        return json.loads(content)
    except Exception as e:
        raise RuntimeError(f"OpenAI call failed: {e}") from e


def extract_job_profile(
    system_prompt: str,
    job_text: str,
    *,
    model: str,
    prompt_cache_key: str,
):
    """
    Extract structured job data via OpenAI Responses Structured Outputs.

    Returns a tuple of (parsed: ExtractionResult, usage: ResponseUsage). The usage
    object is required by the caller to track cached_tokens / input_tokens for
    observability — this is how we verify the >=30% cache target from issue #13.

    Uses an explicit input array (role: "system" + role: "user") so the system
    prompt is part of the cacheable prefix. `prompt_cache_key` ensures consistent
    cache routing across calls within a run.

    Errors:
    - Network / rate-limit / 5xx: propagate the SDK exception unchanged.
    - LLM returned no parseable structured output: raise MalformedOutputError.
    """
    client = get_openai_client()
    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"<job_description>\n{job_text}\n</job_description>",
                    }
                ],
            },
        ],
        text_format=ExtractionResult,
        prompt_cache_key=prompt_cache_key,
    )

    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise MalformedOutputError("Model returned no parsed structured output")
    return parsed, response.usage


def extract_resume_profile(
    system_prompt: str,
    resume_text: str,
    *,
    model: str,
    prompt_cache_key: str,
):
    from models.user_profile import ResumeExtractionResult
    client = get_openai_client()
    response = client.responses.parse(
        model=model,
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"<resume>\n{resume_text}\n</resume>",
                    }
                ],
            },
        ],
        text_format=ResumeExtractionResult,
        prompt_cache_key=prompt_cache_key,
    )
    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise MalformedOutputError("Model returned no parsed structured output")
    return parsed, response.usage
