import os
import re
import unidecode
import logging
from typing import List, Dict, Optional
from supabase import create_client

# تنظیمات لاگ
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# متغیرهای محیطی Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Both SUPABASE_URL and SUPABASE_KEY must be set.")

# اتصال به Supabase
client = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE_NAME = "video_episodes"


def _is_error(response) -> bool:
    status = getattr(response, "status_code", None)
    return status is not None and status >= 300


def generate_slug(title: str) -> str:
    """
    ساخت slug به فرمت: anime-title-s{season}-ep{episode}-{quality}
    از عنوان خام استخراج کیفیت، فصل و قسمت
    """
    text = unidecode.unidecode(title).lower()

    # حذف تگ‌ها و نویز
    text = re.sub(r"\[[^\]]*\]", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"(hardsub|softsub|sub|هاردساب|سافتساب)", "", text, flags=re.IGNORECASE)

    # استخراج کیفیت
    qm = re.search(r"(480|720|1080|2160)[pP]?", text)
    quality = qm.group(1) if qm else "unknown"

    # استخراج فصل
    season = "1"
    sm = re.search(r"(?:season|s)\s*([0-9]{1,2})", text, re.IGNORECASE)
    if sm:
        season = sm.group(1).zfill(1)

    # استخراج قسمت
    episode = "unknown"
    em = re.search(r"(?:e|ep)?\s?(\d{1,4})", text, re.IGNORECASE)
    if em:
        episode = em.group(1).lstrip('0') if em.group(1).lstrip('0') else '0'

    # حذف بخش‌های استخراج‌شده
    text = re.sub(r"(?:season|s)\s*\d{1,2}", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:ep?|e)\s?\d{1,4}", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:480|720|1080|2160)[pP]?", "", text)

    # تبدیل به slug
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")

    return f"{text}-s{season}-ep{episode}-{quality}"


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
    """
    اضافه کردن اپیزود به دیتابیس.
    اگر code موجود نباشد، به صورت خودکار از title ساخته می‌شود.
    """
    try:
        if not episode.get("code"):
            title = episode.get("title", "")
            episode["code"] = generate_slug(title)

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
        logger.error(f"Error updating episode {title}: {e}", exc_info=True)
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
