import os
import threading
import random
from datetime import datetime, timezone, timedelta
from keep_alive import keep_alive
from anime_checker import check_animes_and_send
import time

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from config import logger
from storage import generate_code, get_episode, add_episode

# --- تنظیمات ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
UPLOAD_CHANNEL = os.getenv("UPLOAD_CHANNEL")  # e.g. "@your_channel"
REQUIRED_CHANNELS = os.getenv("REQUIRED_CHANNELS", "").split(",")
admin_ids_env = os.getenv("ADMIN_CHAT_IDS", "")
ADMIN_CHAT_IDS = [int(x) for x in admin_ids_env.split(",") if x.strip()]

if not BOT_TOKEN or not UPLOAD_CHANNEL:
    raise ValueError("BOT_TOKEN and UPLOAD_CHANNEL must be set in environment variables.")

bot = telebot.TeleBot(BOT_TOKEN)

THANK_YOU_MESSAGES = [
    "💛 ممنون از انتخاب PotatoAnime! بازم سر بزن!",
    "🎉 دمت گرم که با ما هستی! PotatoAnime همیشه کنارته!",
    "🍿 از تماشای انیمه لذت ببر! مرسی که با مایی!",
    "✨ یه قدم نزدیک‌تر به دنیای انیمه! ممنون که هستی 🙌",
    "🍥 با ما همیشه یه انیمه خفن منتظرته! مرسی از انتخابت!",
]

def anime_checker_loop():
    last_checked = datetime.now(timezone.utc) - timedelta(minutes=5)
    while True:
        last_checked = check_animes_and_send(last_checked)
        time.sleep(60)


def check_subscriptions(user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        channel = channel.strip()
        if not channel:
            continue
        try:
            status = bot.get_chat_member(chat_id=channel, user_id=user_id).status
            if status not in ["member", "creator", "administrator"]:
                return False
        except Exception as e:
            logger.error(f"Error checking membership for {channel}: {e}", exc_info=True)
            return False
    return True


def schedule_deletion(chat_id: int, message_id: int, delay: int = 30):
    def delete():
        try:
            bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.error(f"Error deleting message {message_id}: {e}", exc_info=True)
    threading.Timer(delay, delete).start()


@bot.message_handler(commands=["start"])
def start_handler(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(
            message.chat.id,
            "⚠️ لطفاً کد اپیزود را بعد از /start وارد کنید.\nمثال: /start Devil_May_Cry-ep1-720"
        )
        return

    code = parts[1].strip()
    if not check_subscriptions(message.from_user.id):
        markup = InlineKeyboardMarkup()
        for ch in REQUIRED_CHANNELS:
            if ch.strip():
                url = f"https://t.me/{ch.lstrip('@')}"
                markup.add(InlineKeyboardButton(f"عضویت در {ch}", url=url))
        markup.add(InlineKeyboardButton("✅ تأیید عضویت", callback_data=f"check_{code}"))
        bot.send_message(
            message.chat.id,
            "لطفاً ابتدا در کانال‌های زیر عضو شوید و سپس تأیید عضویت را فشار دهید:",
            reply_markup=markup
        )
        return

    ep = get_episode(code)
    if not ep:
        bot.send_message(
            message.chat.id,
            f"❌ اپیزودی با کد `{code}` پیدا نشد.",
            parse_mode="Markdown"
        )
        return

    try:
        sent = bot.forward_message(
            chat_id=message.chat.id,
            from_chat_id=UPLOAD_CHANNEL,
            message_id=ep['message_id']
        )
        thank_you = random.choice(THANK_YOU_MESSAGES) + " ⏰ این پیام تا 30 ثانیه دیگر حذف خواهد شد."
        warn = bot.send_message(message.chat.id, thank_you)
        schedule_deletion(message.chat.id, sent.message_id, delay=30)
        schedule_deletion(message.chat.id, warn.message_id, delay=30)
    except Exception as e:
        logger.error(f"Error forwarding episode {code}: {e}", exc_info=True)
        bot.send_message(
            message.chat.id,
            "❌ خطا در ارسال اپیزود. لطفاً مجدداً تلاش کنید."
        )


@bot.callback_query_handler(func=lambda c: c.data.startswith("check_"))
def callback_check(query):
    code = query.data.split("_", 1)[1]
    if not check_subscriptions(query.from_user.id):
        bot.answer_callback_query(query.id, "⚠️ هنوز عضو همه کانال‌ها نیستید.")
        return
    try:
        ep = get_episode(code)
        if not ep:
            bot.answer_callback_query(query.id, "❌ اپیزود پیدا نشد.")
            return
        sent = bot.forward_message(
            chat_id=query.message.chat.id,
            from_chat_id=UPLOAD_CHANNEL,
            message_id=ep['message_id']
        )
        thank_you = random.choice(THANK_YOU_MESSAGES) + " ⏰ این پیام تا ۳۰ ثانیه دیگر حذف خواهد شد."
        warn = bot.send_message(query.message.chat.id, thank_you)
        schedule_deletion(query.message.chat.id, sent.message_id, delay=30)
        schedule_deletion(query.message.chat.id, warn.message_id, delay=30)
        bot.answer_callback_query(query.id)
    except Exception as e:
        logger.error(f"Error in callback forwarding {code}: {e}", exc_info=True)
        bot.answer_callback_query(query.id, "❌ خطا در ارسال اپیزود.")


@bot.channel_post_handler(content_types=['video', 'document'])
def handle_channel_post(message: Message):
    logger.info(f"📥 پیام جدید از کانال دریافت شد: chat_id={message.chat.id}, username={message.chat.username}")

    expected_channel = UPLOAD_CHANNEL.lstrip('@')
    if message.chat.username != expected_channel:
        logger.warning(
            f"⛔️ پیام از کانال اشتباه دریافت شد. انتظار داشتیم: {expected_channel}، اما دریافت شد: {message.chat.username}"
        )
        return

    # دریافت اسم فایل و file_id
    if message.document:
        file_name = message.document.file_name
        file_id = message.document.file_id
    elif message.video:
        file_name = message.caption or 'video'
        file_id = message.video.file_id
    else:
        logger.warning("⛔️ فایل نامعتبر یا بدون نام.")
        return

    code = generate_code(file_name)
    logger.info(f"📦 کد اپیزود تولید‌شده: {code}")

    episode = {
        'code': code,
        'message_id': message.message_id,
        'title': file_name,
        'file_id': file_id,
        'date_added': datetime.now(timezone.utc).isoformat()
    }

    success = add_episode(episode)
    if success:
        logger.info(f"✅ اپیزود {code} با موفقیت ذخیره شد.")
        # اطلاع به ادمین‌ها (اختیاری)
        for admin_id in ADMIN_CHAT_IDS:
            try:
                bot.send_message(admin_id, f"✅ اپیزود جدید ثبت شد: `{code}`", parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Error notifying admin {admin_id}: {e}", exc_info=True)
    else:
        logger.error(f"❌ خطا در ذخیره اپیزود {code}.")


if __name__ == '__main__':
    logger.info("Bot started... polling")
    threading.Thread(target=anime_checker_loop, daemon=True).start()
    keep_alive()
    bot.infinity_polling()
