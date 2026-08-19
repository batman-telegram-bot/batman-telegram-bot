# -*- coding: utf-8 -*-
"""
downloader.py
================
دانلودر اینستاگرام / یوتیوب / پینترست با منوی سه‌گزینه‌ای.

نحوه‌ی کار:
    ۱. کاربر کلمه‌ی «دانلودر» رو می‌نویسه (بدون / و بدون اسم ربات).
    ۲. یه منوی سه‌دکمه‌ای میاد: 📸 اینستاگرام / ▶️ یوتیوب / 📌 پینترست
    ۳. کاربر یکی رو انتخاب می‌کنه.
    ۴. کاربر لینک رو تو همون چت می‌فرسته.
    ۵. ربات با yt-dlp دانلود می‌کنه و ویدیو/عکس رو مستقیم تو چت می‌فرسته.
       برای یوتیوب، حجم فایل هم تو کپشن نشون داده می‌شه.

نیازمندی: yt-dlp باید تو requirements.txt باشه (اضافه شده).

نحوه‌ی اتصال (کنار بقیه‌ی register_ها تو bot.py):

    from downloader import register_downloader
    register_downloader(app)     # <-- این خط رو اضافه کن
"""

import os
import re
import asyncio
import logging
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

log = logging.getLogger(__name__)

try:
    import yt_dlp
except ImportError:  # اگه نصب نشده باشه، پیام واضح می‌دیم به‌جای کرش
    yt_dlp = None


PENDING_DL = {}  # user_id -> "instagram" | "youtube" | "pinterest"

PLATFORM_LABELS = {
    "instagram": "📸 اینستاگرام",
    "youtube": "▶️ یوتیوب",
    "pinterest": "📌 پینترست",
}

# برای هر پلتفرم، محدود کردن دانلود فقط به دامنه‌های همون پلتفرم (جلوی سوءاستفاده رو می‌گیره)
PLATFORM_DOMAINS = {
    "instagram": ("instagram.com", "instagr.am"),
    "youtube": ("youtube.com", "youtu.be", "m.youtube.com"),
    "pinterest": ("pinterest.com", "pin.it"),
}

URL_RE = re.compile(r"https?://\S+")

DOWNLOADER_HELP_TEXT = (
    "📥 دانلودر — بنویس «دانلودر»، پلتفرم (اینستاگرام/یوتیوب/پینترست) رو با دکمه انتخاب کن، "
    "بعد لینک رو همونجا بفرست. برای یوتیوب حجم فایل هم تو کپشن نشون داده می‌شه.\n"
)


def _dl_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(PLATFORM_LABELS["instagram"], callback_data="dl:pick:instagram")],
        [InlineKeyboardButton(PLATFORM_LABELS["youtube"], callback_data="dl:pick:youtube")],
        [InlineKeyboardButton(PLATFORM_LABELS["pinterest"], callback_data="dl:pick:pinterest")],
    ])


def _human_size(num_bytes):
    if not num_bytes:
        return "نامشخص"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


async def downloader_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "📥 دانلودر گاتهام\n\nاول پلتفرم رو انتخاب کن، بعد لینک رو همینجا بفرست.",
        reply_markup=_dl_menu_markup(),
    )


async def downloader_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    platform = q.data.split(":")[2]
    PENDING_DL[q.from_user.id] = platform
    await q.edit_message_text(
        f"{PLATFORM_LABELS[platform]} انتخاب شد ✅\n🔗 حالا لینک رو همینجا بفرست تا برات دانلودش کنم."
    )
    await q.answer()


def _yt_dlp_download(url: str, outdir: str):
    """بلاک‌کننده‌ست — حتماً باید تو asyncio.to_thread صدا زده بشه."""
    ydl_opts = {
        "outtmpl": os.path.join(outdir, "%(id)s.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": 49 * 1024 * 1024,  # سقف ۴۹ مگابایت — محدودیت آپلود بات‌های تلگرام
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
    return filepath, info


async def downloader_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    uid = update.effective_user.id
    text = (msg.text or "").strip()

    match = URL_RE.search(text)
    if not match:
        return  # این پیام لینک نیست، به بقیه‌ی هندلرها بسپار

    if uid not in PENDING_DL:
        return  # کسی پلتفرم انتخاب نکرده، این لینک مال دانلودر نیست

    platform = PENDING_DL.pop(uid)
    url = match.group(0)

    allowed_domains = PLATFORM_DOMAINS[platform]
    if not any(d in url.lower() for d in allowed_domains):
        await msg.reply_text(
            f"⚠️ این لینک برای {PLATFORM_LABELS[platform]} نیست. دوباره «دانلودر» رو بزن و پلتفرم درست رو انتخاب کن."
        )
        return

    if yt_dlp is None:
        await msg.reply_text("⚠️ ماژول دانلود نصب نشده. باید yt-dlp تو requirements.txt باشه (اضافه شده، فقط دیپلوی دوباره لازمه).")
        return

    status = await msg.reply_text(f"⏳ در حال دانلود از {PLATFORM_LABELS[platform]}...")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            filepath, info = await asyncio.to_thread(_yt_dlp_download, url, tmpdir)
        except Exception as e:
            log.warning(f"downloader failed for {url}: {e}")
            await status.edit_text(
                "❌ دانلود ناموفق بود. لینک رو چک کن یا شاید محتوا خصوصی/حذف‌شده باشه.\n"
                f"جزئیات فنی: {str(e)[:200]}"
            )
            return

        if not filepath or not os.path.exists(filepath):
            await status.edit_text("❌ فایل پیدا نشد؛ لینک رو دوباره چک کن.")
            return

        real_size = os.path.getsize(filepath)
        title = (info.get("title") or "").strip()
        caption = title
        if platform == "youtube":
            caption = f"{title}\n📦 حجم: {_human_size(real_size)}" if title else f"📦 حجم: {_human_size(real_size)}"

        ext = os.path.splitext(filepath)[1].lower()
        try:
            with open(filepath, "rb") as f:
                if ext in (".jpg", ".jpeg", ".png", ".webp"):
                    await msg.reply_photo(f, caption=caption or None)
                else:
                    await msg.reply_video(f, caption=caption or None, supports_streaming=True)
        except Exception as e:
            log.warning(f"send failed, fallback to document: {e}")
            try:
                with open(filepath, "rb") as f:
                    await msg.reply_document(f, caption=caption or None)
            except Exception as e2:
                await status.edit_text(f"❌ فایل دانلود شد ولی ارسالش شکست خورد (احتمالاً حجمش زیاده): {str(e2)[:150]}")
                return

        try:
            await status.delete()
        except Exception:
            pass


def register_downloader(app):
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^\s*(دانلودر|دانلود)\s*$"), downloader_menu), group=6)
    app.add_handler(CallbackQueryHandler(downloader_pick_callback, pattern=r"^dl:pick:"), group=6)
    # این هندلر با هر پیام متنی چک می‌کنه که آیا لینک‌شده و منتظرشیم؛ وگرنه هیچ کاری نمی‌کنه
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader_link_handler), group=6)
