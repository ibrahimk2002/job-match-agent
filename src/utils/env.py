import os
from dotenv import load_dotenv

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
load_dotenv(os.path.join(_PROJECT_ROOT, '.env'))

class Config:
    OPENAI_API_KEY: str
    
    def __init__(self):
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise RuntimeError("Missing OPENAI_API_KEY")
        self.OPENAI_API_KEY = openai_key


config = Config()
