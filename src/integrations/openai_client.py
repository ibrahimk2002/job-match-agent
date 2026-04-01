from openai import OpenAI
from utils.config import config
import json

def get_openai_client() -> OpenAI:
    return OpenAI(api_key=config.OPENAI_API_KEY)


def call_llm(prompt):
    client = get_openai_client()

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned empty content")

        return json.loads(content.strip())
    except Exception as e:
        print(f"OpenAI error: {e}")
        return {"error": "Failed to call LLM"}
