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
# نکته: از substring match استفاده می‌کنیم، پس زیردامنه‌ها (uk.pinterest.com,
# www.instagram.com, m.youtube.com و ...) خودکار پوشش داده می‌شن.
PLATFORM_DOMAINS = {
    "instagram": ("instagram.com", "instagr.am"),
    "youtube": ("youtube.com", "youtu.be"),
    "pinterest": ("pinterest.com", "pin.it", "pinimg.com"),
}

# فایل کوکی اختیاری برای هر پلتفرم — بعضی لینک‌های یوتیوب/اینستاگرام پشت قفل
# ضد-ربات‌ان («Sign in to confirm you're not a bot» / «empty media response»)
# و بدون کوکیِ یه اکانت لاگین‌شده اصلاً قابل دانلود نیستن؛ این یه محدودیت سمت
# خود پلتفرمه، نه باگ کد. اگه این env varها ست بشن (مسیر یه فایل cookies.txt به
# فرمت Netscape که از مرورگر export شده)، ازشون استفاده می‌کنیم.
COOKIES_FILES = {
    "instagram": os.getenv("IG_COOKIES_FILE"),
    "youtube": os.getenv("YT_COOKIES_FILE"),
    "pinterest": os.getenv("PIN_COOKIES_FILE"),
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

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


def _base_ydl_opts(outdir: str, platform: str) -> dict:
    opts = {
        "outtmpl": os.path.join(outdir, "%(id)s.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": 49 * 1024 * 1024,  # سقف ۴۹ مگابایت — محدودیت آپلود بات‌های تلگرام
        "retries": 3,
        "fragment_retries": 3,
        "http_headers": {"User-Agent": USER_AGENT},
        "geo_bypass": True,
    }
    cookies_file = COOKIES_FILES.get(platform)
    if cookies_file and os.path.exists(cookies_file):
        opts["cookiefile"] = cookies_file
    return opts


def _yt_dlp_download(url: str, outdir: str, platform: str):
    """بلاک‌کننده‌ست — حتماً باید تو asyncio.to_thread صدا زده بشه.

    برای یوتیوب چند تا player_client رو پشت‌سرهم امتحان می‌کنیم، چون بعضی‌هاشون
    (مثل android/ios) گاهی قفل «Sign in to confirm you're not a bot» رو دور
    می‌زنن حتی بدون کوکی، ولی تضمینی نیست — اگه یوتیوب واقعاً لینک رو قفل کرده
    باشه، تنها راه قطعی فایل کوکیِ یه اکانت لاگین‌شده‌ست (YT_COOKIES_FILE).
    """
    base = _base_ydl_opts(outdir, platform)
    attempts = [{}]
    if platform == "youtube":
        attempts = [
            {"extractor_args": {"youtube": {"player_client": ["android"]}}},
            {"extractor_args": {"youtube": {"player_client": ["ios"]}}},
            {"extractor_args": {"youtube": {"player_client": ["web"]}}},
        ]

    last_err = None
    for extra in attempts:
        opts = {**base, **extra}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
            return filepath, info
        except Exception as e:
            last_err = e
            continue
    raise last_err


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
            filepath, info = await asyncio.to_thread(_yt_dlp_download, url, tmpdir, platform)
        except Exception as e:
            log.warning(f"downloader failed for {url}: {e}")
            err_text = str(e)
            if "Sign in to confirm" in err_text or "not a bot" in err_text:
                await status.edit_text(
                    "❌ یوتیوب برای این لینک قفل ضد-ربات گذاشته و بدون فایل کوکیِ یه اکانت "
                    "لاگین‌شده قابل دور زدن نیست — این محدودیت خود یوتیوبه، نه باگ ربات.\n"
                    "اگه مالک ربات هستی، env var به اسم YT_COOKIES_FILE ست کن (مسیر یه فایل "
                    "cookies.txt که از مرورگر لاگین‌شده export شده)."
                )
            elif "empty media response" in err_text or "login" in err_text.lower():
                await status.edit_text(
                    "❌ اینستاگرام برای این پست جواب خالی داد — یا پست خصوصیه، یا اینستاگرام "
                    "بدون لاگین اجازه‌ی دیدنش رو نمی‌ده. این محدودیت خود اینستاگرامه.\n"
                    "اگه مالک ربات هستی، env var به اسم IG_COOKIES_FILE ست کن."
                )
            else:
                await status.edit_text(
                    "❌ دانلود ناموفق بود. لینک رو چک کن یا شاید محتوا خصوصی/حذف‌شده باشه.\n"
                    f"جزئیات فنی: {err_text[:200]}"
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
