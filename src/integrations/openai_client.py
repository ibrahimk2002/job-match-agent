import os
import dotenv
dotenv.load_dotenv()
from openai import OpenAI
from utils.config import config
import json

import sys

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.job_profile import JobProfile
from config.job_profile import ExtractionResult

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


def extract_job_profile(system_prompt: str, job_text: str, model: str = "gpt-4.1-nano") -> ExtractionResult:
    """
    Extract structured job data using Responses Structured Outputs.
    Returns a validated ExtractionResult object.
    """
    client = get_openai_client()
    try:
        response = client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": job_text},
            ],
            text_format=ExtractionResult,
        )
    except Exception as e:
        raise RuntimeError(f"Structured extraction request failed: {e}") from e

    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise RuntimeError("Model returned no parsed structured output")
    return parsed