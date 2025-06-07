import os
import logging
from typing import List, Dict, Optional
from supabase import create_client

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Both SUPABASE_URL and SUPABASE_KEY must be set.")

client = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE_NAME = "video_episodes"

def _is_error(response) -> bool:
    status = getattr(response, "status_code", None)
    return status is not None and status >= 300

def load_episodes() -> List[Dict]:
    try:
        res = client.table(TABLE_NAME).select("*").order("date_added", desc=False).execute()
        if _is_error(res):
            logger.error(f"Supabase select failed: status {res.status_code}")
            return []
        return res.data or []
    except Exception as e:
        logger.error(f"Error loading episodes: {e}", exc_info=True)
        return []

def get_episode(title: str) -> Optional[Dict]:
    try:
        res = client.table(TABLE_NAME).select("*").eq("title", title).single().execute()
        if _is_error(res):
            logger.error(f"Supabase get failed: status {res.status_code}")
            return None
        return res.data
    except Exception as e:
        logger.error(f"Error getting episode {title}: {e}", exc_info=True)
        return None

def add_episode(episode: Dict) -> bool:
    try:
        res = client.table(TABLE_NAME).insert(episode).execute()
        if _is_error(res):
            logger.error(f"Supabase insert failed: status {res.status_code}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error inserting episode: {e}", exc_info=True)
        return False

def update_episode(title: str, updates: Dict) -> bool:
    try:
        res = client.table(TABLE_NAME).update(updates).eq("title", title).execute()
        if _is_error(res):
            logger.error(f"Supabase update failed: status {res.status_code}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error updating episode {code}: {e}", exc_info=True)
        return False

def delete_episode(code: str) -> bool:
    try:
        res = client.table(TABLE_NAME).delete().eq("code", code).execute()
        if _is_error(res):
            logger.error(f"Supabase delete failed: status {res.status_code}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error deleting episode {code}: {e}", exc_info=True)
        return False
