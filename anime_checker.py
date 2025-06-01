import os
import logging
from datetime import datetime, timezone, timedelta
from supabase import create_client
import telebot

# تنظیمات لاگ‌گیری
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# متغیرهای محیطی
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

# بررسی صحت متغیرها
if not SUPABASE_URL or not SUPABASE_KEY or not BOT_TOKEN or not GROUP_CHAT_ID:
    raise ValueError("لطفاً SUPABASE_URL، SUPABASE_KEY، BOT_TOKEN و GROUP_CHAT_ID را تنظیم کنید.")

# ایجاد کلاینت Supabase و ربات تلگرام
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(BOT_TOKEN)

TABLE_NAME = "potato_anim"

# ساخت پیام کارت انیمه
def format_anime_card(anime: dict) -> str:
    title = anime.get("title", "بدون نام")
    description = anime.get("description", "ندارد")
    status = anime.get("status", "نامشخص")
    genres = anime.get("genres") or []
    genres_text = " ، ".join(genres) if isinstance(genres, list) else str(genres)
    episodes = anime.get("episodes", 0)
    subtitle = anime.get("age_rating", "نامشخص")
    season = anime.get("season", "نامشخص")
    link = anime.get("link") or ""

    episode_list = ""
    for i in range(1, episodes + 1):
        episode_list += f"📍 قسمت {i}: 1080 | 720 | 480\n"

    card = (
        "🥔 P O T A T O   A N I M E\n\n"
        f"📺 نام انیمه: {title}\n"
        f"📖 خلاصه: {description}\n\n"
        f"📊 وضعیت: {status}\n"
        f"🎬 ژانر: {genres_text}\n"
        f"🌀 تعداد فصل‌ها: {season}\n"
        f"🎧 زیرنویس: {subtitle}\n\n"
        "📦 لیست قسمت‌ها:\n\n"
        f"{episode_list}\n"
        "📥 در صورتی که ربات کار نکند، فایل‌ها را می‌توانید به‌صورت دستی از اینجا پیدا کنید.\n\n"
        "───────\n"
    )
    if link:
        card += f"📢 {link}\n"
    return card

# گرفتن انیمه‌های جدید یا تغییر یافته از Supabase
def fetch_new_or_updated_animes(since: datetime):
    try:
        iso_time = since.isoformat()
        response = (
            supabase
            .table(TABLE_NAME)
            .select("*")
            .order("updated_at", desc=True)
            .execute()
        )
        all_data = response.data or []

        filtered = [
            anime for anime in all_data
            if anime.get("created_at", "") >= iso_time or anime.get("updated_at", "") >= iso_time
        ]

        logger.info(f"📦 تعداد انیمه‌های جدید یا به‌روزشده: {len(filtered)}")
        return filtered

    except Exception as e:
        logger.error(f"⚠️ خطا در fetch_new_or_updated_animes: {e}", exc_info=True)
        return []


def check_animes_and_send(last_checked: datetime = None) -> datetime:
    # اگر زمان آخر بررسی مشخص نشده، همه انیمه‌ها بررسی شوند (از سال 2000 به بعد)
    if last_checked is None:
        last_checked = datetime(2000, 1, 1, tzinfo=timezone.utc)

    logger.info(f"🔍 بررسی انیمه‌ها از: {last_checked.isoformat()}")
    animes = fetch_new_or_updated_animes(last_checked)

    if animes:
        logger.info(f"✅ {len(animes)} انیمه جدید یا آپدیت شده پیدا شد.")
        for anime in animes:
            msg = format_anime_card(anime)
            try:
                bot.send_message(GROUP_CHAT_ID, msg)
                logger.info(f"📤 انیمه «{anime.get('title', 'بدون نام')}» ارسال شد.")
            except Exception as e:
                logger.error(f"❌ خطا در ارسال پیام: {e}", exc_info=True)

        updated_times = []
        for a in animes:
            ut = a.get("updated_at")
            if ut:
                try:
                    dt = datetime.fromisoformat(ut)
                    updated_times.append(dt)
                except Exception:
                    pass
        if updated_times:
            return max(updated_times)
    else:
        logger.info("📭 انیمه‌ای برای ارسال وجود ندارد.")

    return last_checked
