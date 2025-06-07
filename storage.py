import os
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime
from supabase import create_client

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Load Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Both SUPABASE_URL and SUPABASE_KEY must be set.")

# Initialize Supabase client
client = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE_NAME = "video_episodes"

# --- Code Generator ---
def generate_code(title: str) -> str:
    """Generates standardized code from file title."""
    # Remove tags like [AWHT]
    clean_title = re.sub(r'\[.*?\]', '', title).strip()
    # Extract quality
    quality_match = re.search(r'(\d{3,4}p)', title)
    quality = quality_match.group(1) if quality_match else 'unknown'
    # Extract season and episode
    match = re.search(r'[Ss](\d+)\s*[-_ ]\s*(\d+)', clean_title)
    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
    else:
        season = 1
        episode = 1
    # Remove season/episode part
    name_only = re.sub(r'[Ss]\d+\s*[-_ ]\s*\d+', '', clean_title).strip()
    # Build code string
    code_base = name_only.lower().replace(' ', '-')
    return f"{code_base}-s{season}-ep{episode}-{quality}"

# --- Supabase operations ---
def _is_error(response) -> bool:
    status = getattr(response, "status_code", None)
    return status is not None and status >= 300

def load_episodes() -> List[Dict]:
    """Fetches all episodes ordered by date_added."""
    try:
        res = client.table(TABLE_NAME).select("*").order("date_added", desc=False).execute()
        if _is_error(res):
            logger.error(f"Supabase select failed: status {res.status_code}")
            return []
        return res.data or []
    except Exception as e:
        logger.error(f"Error loading episodes: {e}", exc_info=True)
        return []

def get_episode(code: str) -> Optional[Dict]:
    """Fetches a single episode by its unique code."""
    try:
        res = client.table(TABLE_NAME).select("*").eq("code", code).single().execute()
        if _is_error(res):
            logger.error(f"Supabase get failed: status {res.status_code}")
            return None
        return res.data
    except Exception as e:
        logger.error(f"Error getting episode {code}: {e}", exc_info=True)
        return None

def add_episode(episode: Dict) -> bool:
    """Inserts a new episode record."""
    try:
        # Add server timestamp if not provided
        if 'date_added' not in episode:
            episode['date_added'] = datetime.utcnow().isoformat()
        res = client.table(TABLE_NAME).insert(episode).execute()
        if _is_error(res):
            logger.error(f"Supabase insert failed: status {res.status_code}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error inserting episode: {e}", exc_info=True)
        return False

def update_episode(code: str, updates: Dict) -> bool:
    """Updates fields of an existing episode identified by code."""
    try:
        res = client.table(TABLE_NAME).update(updates).eq("code", code).execute()
        if _is_error(res):
            logger.error(f"Supabase update failed: status {res.status_code}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error updating episode {code}: {e}", exc_info=True)
        return False

def delete_episode(code: str) -> bool:
    """Deletes an episode by its unique code."""
    try:
        res = client.table(TABLE_NAME).delete().eq("code", code).execute()
        if _is_error(res):
            logger.error(f"Supabase delete failed: status {res.status_code}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error deleting episode {code}: {e}", exc_info=True)
        return False
