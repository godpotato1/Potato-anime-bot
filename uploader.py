import os
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from storage import generate_code, add_episode

# متغیر محیطی کانال آپلود
UPLOAD_CHANNEL = os.getenv('UPLOAD_CHANNEL')
if not UPLOAD_CHANNEL:
    raise ValueError('UPLOAD_CHANNEL must be set.')

async def handle_new_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles new uploads in the specified channel and stores episodes automatically."""
    message = update.message
    # فقط پیام‌های کانال آپلود را پردازش کن
    if not message or not message.chat or message.chat.username.lower() != UPLOAD_CHANNEL.lstrip('@').lower():
        return

    # دریافت اسم فایل و file_id
    if message.document:
        file_name = message.document.file_name
        file_id = message.document.file_id
    elif message.video:
        file_name = message.caption or 'video'
        file_id = message.video.file_id
    else:
        # اگر فایل نبود (متن یا غیره)
        return

    # تولید کد استاندارد از عنوان فایل
    code = generate_code(file_name)

    # آماده‌سازی دیتا برای ذخیره‌سازی
    episode = {
        'message_id': message.message_id,
        'code': code,
        'title': file_name,
        'file_id': file_id,
        'date_added': datetime.utcnow().isoformat()
    }

    # ذخیره در Supabase
    success = add_episode(episode)

    # اطلاع به کاربر uploader (در پیوی) در مورد نتیجه ذخیره
    target_chat = update.effective_user.id
    await context.bot.send_message(
        chat_id=target_chat,
        text=(
            f"{'✅' if success else '❌'} فایل شما "
            f"{'با موفقیت ثبت شد' if success else 'ثبت نشد'}:\n"
            f"🎬 `{file_name}`\n"
            f"🔑 کد: `{code}`"
        ),
        parse_mode='Markdown'
    )
