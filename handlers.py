# handlers.py

import os
import threading
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from config import logger
from storage import get_episode, add_episode

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
UPLOAD_CHANNEL = os.getenv("UPLOAD_CHANNEL")  # e.g. "@your_channel"
REQUIRED_CHANNELS = os.getenv("REQUIRED_CHANNELS", "").split(",")
telebot.apihelper.proxy = {
    'http': os.getenv('SOCKS5_PROXY'),
    'https': os.getenv('SOCKS5_PROXY')
}

if not BOT_TOKEN or not UPLOAD_CHANNEL:
    raise ValueError("BOT_TOKEN and UPLOAD_CHANNEL must be set in environment variables.")

bot = telebot.TeleBot(BOT_TOKEN)


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


def _extract_quality(code: str) -> int:
    try:
        return int(code.split("_")[-1])
    except:
        return 0


@bot.message_handler(commands=["start"])
def start_handler(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(
            message.chat.id,
            "⚠️ لطفاً کد اپیزود را بعد از /start وارد کنید.\nمثال: /start Devil_May_Cry_ep1_720"
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
        warn = bot.send_message(
            message.chat.id,
            "⏰ این پیام تا 30 ثانیه دیگر حذف خواهد شد."
        )
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
        warn = bot.send_message(query.message.chat.id, "⏰ این پیام تا 30 ثانیه دیگر حذف خواهد شد.")
        schedule_deletion(query.message.chat.id, sent.message_id, delay=30)
        schedule_deletion(query.message.chat.id, warn.message_id, delay=30)
        bot.answer_callback_query(query.id)
    except Exception as e:
        logger.error(f"Error in callback forwarding {code}: {e}", exc_info=True)
        bot.answer_callback_query(query.id, "❌ خطا در ارسال اپیزود.")


@bot.channel_post_handler(content_types=['video', 'document'])
def handle_channel_post(message: Message):
    # فقط کانال صحیح
    if message.chat.username != UPLOAD_CHANNEL.lstrip('@'):
        return

    # تلاش برای گرفتن نام فایل به عنوان code
    code = None
    if message.document:
        code = message.document.file_name.rsplit('.', 1)[0]  # remove extension
    elif message.video and message.caption:
        code = message.caption.strip()

    if not code:
        logger.warning("No code found in channel post.")
        return

    episode = {
        'code': code,
        'message_id': message.message_id,
        'date_added': datetime.now().isoformat(),
        'title': code,
        'quality': _extract_quality(code)
    }

    if add_episode(episode):
        logger.info(f"✅ Episode '{code}' inserted from channel.")
    else:
        logger.warning(f"❌ Failed to insert episode '{code}'.")


if __name__ == '__main__':
    logger.info("Bot started... polling")
    bot.infinity_polling()
