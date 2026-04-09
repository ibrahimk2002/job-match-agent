import os
import dotenv
dotenv.load_dotenv()  # Load environment variables from .env file
from openai import OpenAI
# from utils.config import config
import json

def get_openai_client() -> OpenAI:
    # return OpenAI(api_key=config.OPENAI_API_KEY)
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def call_llm(prompt: str):
    client = get_openai_client()

    try:
        response = client.responses.create(
            model="gpt-4.1-nano",
            input=prompt,
        )
        content = response.output_text
        if not content:
            raise ValueError("LLM returned empty content")

        return content
    except Exception as e:
        print(f"OpenAI error: {e}")
        return {"error": "Failed to call LLM"}

output = call_llm("What is agent orchestration?")
print(output)