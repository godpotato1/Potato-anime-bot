import os
import logging
import threading
import random
import re
import time
from datetime import datetime, timezone, timedelta

from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from keep_alive import keep_alive
from anime_checker import check_animes_and_send
from config import logger
from storage import add_episode, get_episode

# --- تنظیمات ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
UPLOAD_CHANNEL = os.getenv("UPLOAD_CHANNEL")  # e.g. "@your_channel"
REQUIRED_CHANNELS = os.getenv("REQUIRED_CHANNELS", "").split(",")
admin_ids_env = os.getenv("ADMIN_CHAT_IDS", "")
ADMIN_CHAT_IDS = [int(x) for x in admin_ids_env.split(",") if x.strip()]

if not BOT_TOKEN or not UPLOAD_CHANNEL:
    raise ValueError("BOT_TOKEN and UPLOAD_CHANNEL must be set in environment variables.")

bot = TeleBot(BOT_TOKEN)
handled_episodes = set()

THANK_YOU_MESSAGES = [
    "💛 ممنون از انتخاب PotatoAnime! بازم سر بزن!",
    "🎉 دمت گرم که با ما هستی! PotatoAnime همیشه کنارته!",
    "🍿 از تماشای انیمه لذت ببر! مرسی که با مایی!",
    "✨ یه قدم نزدیک‌تر به دنیای انیمه! ممنون که هستی 🙌",
    "🍥 با ما همیشه یه انیمه خفن منتظرته! مرسی از انتخابت!",
]

def generate_title(raw: str) -> str:
    # 1. حذف تگ‌های مربعی
    no_tags = re.sub(r"\[.*?\]", "", raw)
    # 2. استخراج کیفیت
    q_match = re.search(r"(\d{3,4})(?=p)", raw, re.IGNORECASE)
    quality = q_match.group(1) if q_match else ""
    # 3. استخراج فصل (Sx)
    s_match = re.search(r"S(\d+)\b", no_tags, re.IGNORECASE)
    season = s_match.group(1).lstrip("0") if s_match else None
    # 4. استخراج قسمت (Ep or last number)
    ep_match = re.search(r"Ep(?:isode)?\s*(\d+)", no_tags, re.IGNORECASE)
    if ep_match:
        episode_num = ep_match.group(1).lstrip("0")
    else:
        nums = re.findall(r"\b(\d+)\b", no_tags)
        # اگر فصل در nums هست، حذفش
        if season and season in nums:
            nums = [n for n in nums if n != season]
        episode_num = nums[-1].lstrip("0") if nums else None
    # 5. پاکسازی نام از فصل، قسمت و کیفیت و اعداد اضافی
    name = no_tags
    name = re.sub(r"S\d+\b", "", name)
    name = re.sub(r"Ep(?:isode)?\s*\d+", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\d{3,4}p", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\b\d+\b", "", name)
    # 6. slugify
    slug = re.sub(r"[^0-9a-zA-Z]+", "-", name).strip("-").lower()
    # 7. گردآوری اجزا
    parts = [slug]
    if season:
        parts.append(f"s{season}")
    if episode_num:
        parts.append(f"ep{episode_num}")
    if quality:
        parts.append(quality)
    return "-".join(parts)

def check_subscriptions(user_id: int) -> bool:
    for ch in REQUIRED_CHANNELS:
        ch = ch.strip()
        if not ch:
            continue
        try:
            status = bot.get_chat_member(chat_id=ch, user_id=user_id).status
            if status not in ["member", "creator", "administrator"]:
                return False
        except Exception as e:
            logger.error(f"Error checking subscription {ch}: {e}", exc_info=True)
            return False
    return True

def schedule_deletion(chat_id: int, message_id: int, delay: int = 30):
    def delete():
        try:
            bot.delete_message(chat_id=chat_id, message_id=message_id)
        except:
            pass
    threading.Timer(delay, delete).start()

def _extract_quality(raw: str) -> int:
    try:
        return int(re.search(r"(\d{3,4})(?=p)", raw).group(1))
    except:
        return 0

def anime_checker_loop():
    last = datetime.now(timezone.utc) - timedelta(minutes=5)
    while True:
        last = check_animes_and_send(last)
        time.sleep(60)

@bot.channel_post_handler(content_types=['video', 'document'])
def handle_channel_post(message: Message):
    if message.chat.username != UPLOAD_CHANNEL.lstrip('@'):
        return

    # استخراج raw title
    if message.document:
        raw = message.document.file_name.rsplit('.', 1)[0]
    else:
        raw = message.caption.strip()

    title = generate_title(raw)
    episode = {
        'code': raw,
        'title': title,
        'message_id': message.message_id,
        'date_added': datetime.now(timezone.utc).isoformat(),
        'quality': _extract_quality(raw),
    }

    if add_episode(episode):
        logger.info(f"✅ اپیزود «{title}» ثبت شد.")
    else:
        logger.error("❌ خطا در ذخیره اپیزود.")

@bot.message_handler(commands=["start"])
def start_handler(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(
            message.chat.id,
            "⚠️ لطفاً slug اپیزود را بعد از /start وارد کنید.\n"
            "مثال: /start wind-breaker-s2-ep6-1080"
        )
        return

    title = parts[1].strip()
    if not check_subscriptions(message.from_user.id):
        markup = InlineKeyboardMarkup()
        for ch in REQUIRED_CHANNELS:
            if ch.strip():
                url = f"https://t.me/{ch.lstrip('@')}"
                markup.add(InlineKeyboardButton(f"عضویت در {ch}", url=url))
        bot.send_message(
            message.chat.id,
            "⚠️ ابتدا عضو کانال‌های زیر شوید:",
            reply_markup=markup
        )
        return

    ep = get_episode(title)
    if not ep:
        bot.send_message(
            message.chat.id,
            f"❌ هیچ اپیزودی با slug `{title}` یافت نشد.",
            parse_mode="Markdown"
        )
        return

    sent = bot.forward_message(message.chat.id, UPLOAD_CHANNEL, ep['message_id'])
    thank = random.choice(THANK_YOU_MESSAGES)
    warn = bot.send_message(message.chat.id, thank + " ⏰ این پیام پس از ۳۰ ثانیه حذف می‌شود.")
    schedule_deletion(message.chat.id, sent.message_id)
    schedule_deletion(message.chat.id, warn.message_id)

if __name__ == '__main__':
    threading.Thread(target=anime_checker_loop, daemon=True).start()
    keep_alive()
    bot.infinity_polling()
