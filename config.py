# config.py
import os
import logging
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Supabase configuration ---
SUPABASE_URL = os.getenv("SUPABASE_URL")  # e.g. https://xyzcompany.supabase.co
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  # anon/public service role key or service_role secret

# Validate configuration
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Both SUPABASE_URL and SUPABASE_KEY must be set in environment variables or .env file.")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Logging configuration ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)
