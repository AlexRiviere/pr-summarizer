import os

from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

OPENAI_MODEL = "gpt-4o-mini"
MAX_DIFF_CHARS = 15_000
