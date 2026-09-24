import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("MODEL")

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

HEADLESS = os.getenv("HEADLESS", "False").lower() == "true"

RESUME_PATH = os.getenv("RESUME_PATH")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")

JOB_KEYWORD = os.getenv("JOB_KEYWORD", "python")
JOB_LOCATION = os.getenv("JOB_LOCATION", "Chennai")
MAX_APPLICATIONS = int(os.getenv("MAX_APPLICATIONS", "30"))