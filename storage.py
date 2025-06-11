import os
import logging
from typing import Optional, Dict
from supabase import create_client

# تنظیم لاگ
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# اتصال به Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials missing")

client = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE_NAME = "video_episodes"

def _is_error(res) -> bool:
    return hasattr(res, "status_code") and res.status_code >= 300

def add_episode(ep: Dict) -> bool:
    try:
        res = client.table(TABLE_NAME).insert(ep).execute()
        if _is_error(res):
            logger.error(f"Insert error: status {res.status_code}")
            return False
        return True
    except Exception as e:
        logger.error(f"Insert exception: {e}", exc_info=True)
        return False

def get_episode(title: str) -> Optional[Dict]:
    try:
        res = (
            client.table(TABLE_NAME)
                  .select("*")
                  .eq("title", title)
                  .single()
                  .execute()
        )
        if _is_error(res):
            logger.error(f"Get error: status {res.status_code}")
            return None
        return res.data
    except Exception as e:
        logger.error(f"Get exception: {e}", exc_info=True)
        return None
