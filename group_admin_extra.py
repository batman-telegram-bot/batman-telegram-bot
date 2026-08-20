# -*- coding: utf-8 -*-
"""
group_admin_extra.py
================
دو ابزار مدیریتی جدید برای «مدیریت گروه»:

    🔒 قفل گروه / باز کردن گروه — با یه کلمه، فرستادن پیام رو برای همه‌ی
       غیرادمین‌ها می‌بنده/باز می‌کنه (برای وقتی گروه شلوغ/بحرانیه).
    🧹 پاکسازی — روی قدیمی‌ترین پیامی که می‌خوای حذفش کنی ریپلای کن و بنویس
       «پاکسازی» تا همه‌ی پیام‌های از اونجا تا الان (حداکثر ۱۰۰ تا) پاک بشن.
"""

import asyncio
import logging

from telegram import Update, ChatPermissions
from telegram.constants import ChatType
from telegram.ext import ContextTypes, MessageHandler, filters

log = logging.getLogger(__name__)

LOCK_RE = filters.Regex(r"(?i)^\s*قفل گروه\s*$")
UNLOCK_RE = filters.Regex(r"(?i)^\s*باز کردن گروه\s*$")
PURGE_RE = filters.Regex(r"(?i)^\s*پاکسازی\s*$") & filters.REPLY

MAX_PURGE = 100


def register_group_admin_extra(app, deps):
    """deps = {"is_group_admin": async(update, context) -> bool}"""

    async def lock_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return
        if not await deps["is_group_admin"](update, context):
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌تونن گروه رو قفل کنن.")
            return
        try:
            await context.bot.set_chat_permissions(
                update.effective_chat.id, ChatPermissions(can_send_messages=False)
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ نشد: {e}")
            return
        await update.message.reply_text("🔒 گروه قفل شد؛ فقط ادمین‌ها می‌تونن پیام بدن.")

    async def unlock_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return
        if not await deps["is_group_admin"](update, context):
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌تونن گروه رو باز کنن.")
            return
        try:
            await context.bot.set_chat_permissions(
                update.effective_chat.id,
                ChatPermissions(
                    can_send_messages=True, can_send_audios=True, can_send_documents=True,
                    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
                    can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ نشد: {e}")
            return
        await update.message.reply_text("🔓 گروه باز شد؛ همه می‌تونن دوباره پیام بدن.")

    async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return
        if not await deps["is_group_admin"](update, context):
            await update.message.reply_text("⛔️ فقط ادمین‌ها می‌تونن پاکسازی کنن.")
            return
        chat_id = update.effective_chat.id
        start_id = update.message.reply_to_message.message_id
        end_id = update.message.message_id
        if end_id - start_id > MAX_PURGE:
            start_id = end_id - MAX_PURGE
        deleted = 0
        for mid in range(start_id, end_id + 1):
            try:
                await context.bot.delete_message(chat_id, mid)
                deleted += 1
            except Exception:
                pass
        try:
            confirm = await context.bot.send_message(chat_id, f"🧹 {deleted} پیام پاک شد.")
            await asyncio.sleep(5)
            await confirm.delete()
        except Exception:
            pass

    app.add_handler(MessageHandler(LOCK_RE, lock_group), group=24)
    app.add_handler(MessageHandler(UNLOCK_RE, unlock_group), group=24)
    app.add_handler(MessageHandler(PURGE_RE, purge), group=24)
