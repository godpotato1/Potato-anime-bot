import os
import re
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

# متغیرها
UPLOAD_CHANNEL = os.environ['UPLOAD_CHANNEL']
ADMIN_CHAT_ID = int(os.environ['ADMIN_CHAT_ID'])

# حافظه موقتی (میشه دیتابیس هم کرد)
database = []

def generate_code(title: str) -> str:
    # حذف تگ‌ها مثل [AWHT]
    name = re.sub(r'\[.*?\]', '', title).strip()

    # استخراج کیفیت
    quality_match = re.search(r'(\d{3,4}p)', title)
    quality = quality_match.group(1) if quality_match else 'unknown'

    # استخراج فصل و قسمت
    match = re.search(r'[Ss](\d+)\s*[-_ ]\s*(\d+)', name)
    if match:
        season = int(match.group(1))
        episode = int(match.group(2))
    else:
        season = 1
        episode = 1

    # حذف فصل و قسمت از اسم
    name = re.sub(r'[Ss]\d+\s*[-_ ]\s*\d+', '', name).strip()

    # تمیزسازی نهایی
    anime_code = name.lower().replace(' ', '-')
    return f"{anime_code}-s{season}-ep{episode}-{quality}"

# دریافت فایل جدید از کانال
async def handle_new_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or message.chat.username.lower() != UPLOAD_CHANNEL.lstrip('@').lower():
        return

    file_name = ""
    if message.document:
        file_name = message.document.file_name
        file_id = message.document.file_id
    elif message.video:
        file_name = message.caption or "video"
        file_id = message.video.file_id
    else:
        return  # اگر neither document nor video

    code = generate_code(file_name)

    # ذخیره در لیست موقتی
    database.append({
        "message_id": message.message_id,
        "code": code,
        "file_id": file_id,
        "date_added": datetime.utcnow().isoformat()
    })

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"📥 فایل جدید ثبت شد:\n\n🎬 `{file_name}`\n🔑 کد: `{code}`",
        parse_mode="Markdown"
    )
