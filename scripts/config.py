import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# API Configuration
TRAFFY_API_BASE_URL = os.getenv(
    "TRAFFY_API_BASE_URL", 
    ""
)

# API Default User Parameters
DEFAULT_API_PARAMS = {
    "name": os.getenv("TRAFFY_USER_NAME", ""),
    "org": os.getenv("TRAFFY_USER_ORG", ""),
    "email": os.getenv("TRAFFY_USER_EMAIL", ""),
    "purpose": os.getenv("TRAFFY_USER_PURPOSE", ""),
    "tel": os.getenv("TRAFFY_USER_TEL", "")
}

# Database Configuration
POSTGRES_USER = os.getenv("POSTGRES_USER", "")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "")

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"