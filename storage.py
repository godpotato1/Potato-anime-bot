import os
import re
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from supabase import create_client

# --- ENV Config ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL و SUPABASE_KEY باید تنظیم شده باشند.")

# --- Supabase Client ---
client = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE_NAME = "video_episodes"

# --- Code Generator ---
def generate_code(title: str) -> str:
    title = re.sub(r'\[.*?\]', '', title).strip()
    quality_match = re.search(r'(\d{3,4}p)', title)
    quality = quality_match.group(1) if quality_match else 'unknown'
    match = re.search(r'[Ss](\d+)\s*[-_ ]\s*(\d+)', title)
    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
    else:
        season = 1
        episode = 1
    title = re.sub(r'[Ss]\d+\s*[-_ ]\s*\d+', '', title).strip()
    code = title.lower().replace(' ', '-')
    return f"{code}-s{season}-ep{episode}-{quality}"

# --- Insert Episode to Supabase ---
def add_episode_to_supabase(data: dict) -> bool:
    try:
        res = client.table(TABLE_NAME).insert(data).execute()
        return not (hasattr(res, "status_code") and res.status_code >= 300)
    except Exception as e:
        print(f"❌ Error inserting to Supabase: {e}")
        return False

# --- Telegram Handler ---
async def handle_new_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return

    file_name = ""
    file_id = ""

    if message.document:
        file_name = message.document.file_name
        file_id = message.document.file_id
    elif message.video:
        file_name = message.caption or "video"
        file_id = message.video.file_id
    else:
        return

    code = generate_code(file_name)

    episode = {
        "message_id": message.message_id,
        "code": code,
        "title": file_name,
        "file_id": file_id,
        "date_added": datetime.utcnow().isoformat()
    }

    success = add_episode_to_supabase(episode)

    await context.bot.send_message(
        chat_id=update.effective_user.id,  # به خود کاربر بفرست
        text=f"{'✅' if success else '❌'} فایل شما {('با موفقیت ثبت شد' if success else 'ثبت نشد')}:\n\n🎬 `{file_name}`\n🔑 کد: `{code}`",
        parse_mode="Markdown"
    )
