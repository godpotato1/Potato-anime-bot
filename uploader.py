import os
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

# متغیرها
UPLOAD_CHANNEL = os.environ['UPLOAD_CHANNEL']
ADMIN_CHAT_ID = int(os.environ['ADMIN_CHAT_ID'])

# دیکشنری برای ذخیره وضعیت عنوان گرفتن (می‌تونی به DB متصل کنی)
pending_titles = {}

# وقتی فایل جدید در کانال آپلود شد
async def handle_new_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or message.chat.username.lower() != UPLOAD_CHANNEL.lstrip('@').lower():
        return

    # ذخیره موقت پیام برای انتظار عنوان
    pending_titles[message.message_id] = {
        "date_added": datetime.utcnow(),
        "message_id": message.message_id,
        "code": None,
        "title": None,
        "quality": None,
    }

    # از ادمین بپرس عنوان فایل
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"فایلی با شناسه پیام {message.message_id} در کانال آپلود شد.\nلطفاً عنوان فایل را ارسال کنید."
    )

# وقتی ادمین عنوان را می‌فرسته
async def handle_title_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_CHAT_ID:
        return

    text = update.message.text.strip()
    # فرض: ادمین اول پیام_id رو می‌فرسته بعد عنوان یا فقط عنوان بسته به روش شما
    # اینجا ساده فرض می‌کنیم فقط عنوان

    # بررسی اینکه آخرین پیام آپلود کدوم بود
    if not pending_titles:
        await update.message.reply_text("هیچ فایل جدیدی برای تعیین عنوان وجود ندارد.")
        return

    # گرفتن آخرین پیام منتظر عنوان
    last_msg_id = list(pending_titles.keys())[-1]
    pending_titles[last_msg_id]['title'] = text

    # اینجا می‌تونی ذخیره در دیتابیس Supabase بزنی (مثلا از async http client)
    # فعلاً فقط تایید می‌کنیم:
    await update.message.reply_text(f"عنوان فایل برای پیام {last_msg_id} ثبت شد: {text}")

    # حذف از pending_titles
    del pending_titles[last_msg_id]
