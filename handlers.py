import os
import threading
import random
import re
import time
from datetime import datetime, timezone, timedelta

from keep_alive import keep_alive
from anime_checker import check_animes_and_send
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import logger
from storage import get_episode, add_episode, generate_slug

# --- تنظیمات ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
UPLOAD_CHANNEL = os.getenv("UPLOAD_CHANNEL", "").lstrip('@').lower()
REQUIRED_CHANNELS = os.getenv("REQUIRED_CHANNELS", "").split(",")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))

if not BOT_TOKEN or not UPLOAD_CHANNEL or not ADMIN_CHAT_ID:
    raise ValueError("BOT_TOKEN, UPLOAD_CHANNEL and ADMIN_CHAT_ID must be set in environment variables.")

bot = telebot.TeleBot(BOT_TOKEN)

THANK_YOU_MESSAGES = [
    "💛 ممنون از انتخاب PotatoAnime! بازم سر بزن!",
    "🎉 دمت گرم که با ما هستی! PotatoAnime همیشه کنارته!",
    "🍿 از تماشای انیمه لذت ببر! مرسی که با مایی!",
    "✨ یه قدم نزدیک‌تر به دنیای انیمه! ممنون که هستی 🙌",
    "🍥 با ما همیشه یه انیمه خفن منتظرته! مرسی از انتخابت!",
]

# استخراج عنوان و کیفیت از عنوان خام برای ثبت

def extract_title_quality(text: str):
    clean = re.sub(r"\[[^\]]*\]", "", text)
    clean = re.sub(r"@\w+", "", clean)
    qm = re.search(r"(480|720|1080|2160)p?", clean, re.IGNORECASE)
    quality = qm.group(1) + 'p' if qm else None
    title = re.sub(r"(480|720|1080|2160)p?", "", clean, flags=re.IGNORECASE).strip()
    return title, quality

# بررسی اشتراک کاربر در کانال‌های مورد نیاز

def check_subscriptions(user_id: int) -> bool:
    for ch in REQUIRED_CHANNELS:
        ch = ch.strip()
        if not ch: continue
        try:
            status = bot.get_chat_member(chat_id=ch, user_id=user_id).status
            if status not in ["member", "creator", "administrator"]:
                return False
        except:
            return False
    return True

# زمان‌بندی حذف پیام‌ها

def schedule_deletion(chat_id: int, message_id: int, delay: int = 30):
    def delete():
        try:
            bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            pass
    threading.Timer(delay, delete).start()

# هدایت دستور /start برای کاربران
@bot.message_handler(commands=["start"])
def start_handler(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id,
                         "⚠️ لطفاً کد اپیزود را پس از /start وارد کنید. مثال: /start one-piece-s21-ep1045-1080")
        return
    code = parts[1].strip()
    if not check_subscriptions(message.from_user.id):
        markup = InlineKeyboardMarkup()
        for ch in REQUIRED_CHANNELS:
            if ch.strip():
                markup.add(InlineKeyboardButton(f"عضویت در {ch}", url=f"https://t.me/{ch.lstrip('@')}") )
        markup.add(InlineKeyboardButton("✅ تأیید عضویت", callback_data=f"check_{code}"))
        bot.send_message(message.chat.id,
                         "لطفاً ابتدا در کانال‌ها عضو شوید و سپس تأیید را بزنید:",
                         reply_markup=markup)
        return
    ep = get_episode(code)
    if not ep:
        bot.send_message(message.chat.id, f"❌ اپیزودی با کد `{code}` پیدا نشد.", parse_mode="Markdown")
        return
    try:
        sent = bot.forward_message(chat_id=message.chat.id, from_chat_id=UPLOAD_CHANNEL, message_id=ep['message_id'])
        thank = random.choice(THANK_YOU_MESSAGES) + " ⏰ این پیام در 30 ثانیه حذف می‌شود."
        warn = bot.send_message(message.chat.id, thank)
        schedule_deletion(message.chat.id, sent.message_id)
        schedule_deletion(message.chat.id, warn.message_id)
    except Exception:
        bot.send_message(message.chat.id, "❌ خطا در ارسال اپیزود. لطفاً دوباره امتحان کنید.")

# هندلر callback برای تأیید عضویت
@bot.callback_query_handler(func=lambda c: c.data.startswith("check_"))
def callback_check(query):
    code = query.data.split("_",1)[1]
    if not check_subscriptions(query.from_user.id):
        bot.answer_callback_query(query.id, "⚠️ هنوز عضو همه کانال‌ها نیستید.")
        return
    ep = get_episode(code)
    if not ep:
        bot.answer_callback_query(query.id, "❌ اپیزود پیدا نشد.")
        return
    try:
        sent = bot.forward_message(chat_id=query.message.chat.id,
                                   from_chat_id=UPLOAD_CHANNEL,
                                   message_id=ep['message_id'])
        thank = random.choice(THANK_YOU_MESSAGES) + " ⏰ این پیام در 30 ثانیه حذف می‌شود."
        warn = bot.send_message(query.message.chat.id, thank)
        schedule_deletion(query.message.chat.id, sent.message_id)
        schedule_deletion(query.message.chat.id, warn.message_id)
        bot.answer_callback_query(query.id)
    except:
        bot.answer_callback_query(query.id, "❌ خطا در ارسال اپیزود.")

# هندلر وقتی کانال آپلود می‌شود
@bot.channel_post_handler(content_types=['video','document'])
def handle_channel_post(message):
    logger.info(f"📥 پیام جدید در کانال: {message.chat.username} id={message.message_id}")
    if message.chat.username.lower() != UPLOAD_CHANNEL:
        return
    filename = getattr(message.document, 'file_name', '')
    caption = message.caption or ''
    src = caption if caption else filename
    title, quality = extract_title_quality(src)
    if not title or not quality:
        bot.send_message(chat_id=ADMIN_CHAT_ID,
                         text=f"❌ استخراج عنوان/کیفیت از پیام {message.message_id} ناموفق: `{src}`",
                         parse_mode="Markdown")
        return
    episode = {
        'title': title,
        'quality': quality,
        'date_added': datetime.now(timezone.utc).isoformat(),
        'message_id': message.message_id
    }
    success = add_episode(episode)
    if success:
        slug = episode.get('code') or generate_slug(title)
        msg = f"✅ اپیزود با کد `{slug}` و عنوان «{title}» با موفقیت ثبت شد."
        bot.send_message(chat_id=f"@{UPLOAD_CHANNEL}", text=msg)
    else:
        bot.send_message(chat_id=ADMIN_CHAT_ID,
                         text=f"❌ خطا در ثبت اپیزود `{title}`", parse_mode="Markdown")

if __name__ == '__main__':
    threading.Thread(target=anime_checker_loop, daemon=True).start()
    keep_alive()
    logger.info("Bot is polling...")
    bot.infinity_polling()
