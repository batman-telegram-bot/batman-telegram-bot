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
import json
import time
import uuid
import shutil
import asyncio
import logging
import mimetypes
import tempfile
import subprocess

import httpx
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, InputMediaVideo,
)
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

log = logging.getLogger(__name__)

try:
    import yt_dlp
except ImportError:  # اگه نصب نشده باشه، پیام واضح می‌دیم به‌جای کرش
    yt_dlp = None


PENDING_DL = {}  # user_id -> "instagram" | "youtube" | "pinterest" | "tiktok" | "twitter" | "soundcloud"

PLATFORM_LABELS = {
    "instagram": "📸 اینستاگرام",
    "youtube": "▶️ یوتیوب",
    "pinterest": "📌 پینترست",
    "tiktok": "🎵 تیک‌تاک",
    "twitter": "🐦 ایکس/توییتر",
    "soundcloud": "🎧 ساندکلاود",
}

# برای هر پلتفرم، محدود کردن دانلود فقط به دامنه‌های همون پلتفرم (جلوی سوءاستفاده رو می‌گیره)
# نکته: از substring match استفاده می‌کنیم، پس زیردامنه‌ها (uk.pinterest.com,
# www.instagram.com, m.youtube.com و ...) خودکار پوشش داده می‌شن.
PLATFORM_DOMAINS = {
    "instagram": ("instagram.com", "instagr.am"),
    "youtube": ("youtube.com", "youtu.be"),
    "pinterest": ("pinterest.com", "pin.it", "pinimg.com"),
    "tiktok": ("tiktok.com",),
    "twitter": ("twitter.com", "x.com"),
    "soundcloud": ("soundcloud.com", "snd.sc"),
}

def _detect_platform_from_url(url: str):
    """اگه کاربر بدون انتخاب پلتفرم (بدون زدن «دانلودر» و بدون کلیک دکمه) مستقیم
    یه لینک پشتیبانی‌شده بفرسته، از روی دامنه‌ش پلتفرم رو خودکار تشخیص بده.
    این دقیقاً همون چیزیه که تو Group لازمه: کاربر لینک می‌فرسته، ربات خودش
    Platform رو تشخیص می‌ده و بدون نیاز به مرحله‌ی انتخاب منو دانلود می‌کنه.
    اگه دامنه به هیچ پلتفرمی نخوره، None برمی‌گرده (پیام بی‌سروصدا به بقیه‌ی
    هندلرها سپرده می‌شه، همون رفتار قبلی برای لینک‌های غیرمرتبط)."""
    u = url.lower()
    for platform, domains in PLATFORM_DOMAINS.items():
        if any(d in u for d in domains):
            return platform
    return None


# فایل کوکی اختیاری برای هر پلتفرم — بعضی لینک‌های یوتیوب/اینستاگرام پشت قفل
# ضد-ربات‌ان («Sign in to confirm you're not a bot» / «empty media response»)
# و بدون کوکیِ یه اکانت لاگین‌شده اصلاً قابل دانلود نیستن؛ این یه محدودیت سمت
# خود پلتفرمه، نه باگ کد. اگه این env varها ست بشن (مسیر یه فایل cookies.txt به
# فرمت Netscape که از مرورگر export شده)، ازشون استفاده می‌کنیم.
# اگه env var ست نشده بود، دنبال یه فایل کوکیِ پیش‌فرض کنار خودِ bot.py می‌گردیم؛
# این‌جوری کافیه فایل cookies.txt خروجی مرورگر (فرمت Netscape) رو با همین اسم‌ها
# تو ریشه‌ی پروژه بذاری، بدون نیاز به تنظیم متغیر محیطی رو هاست.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _default_cookie_path(*names):
    for name in names:
        path = os.path.join(_BASE_DIR, name)
        if os.path.exists(path):
            return path
    return None


COOKIES_FILES = {
    "instagram": os.getenv("IG_COOKIES_FILE") or _default_cookie_path(
        "instagram_cookies.txt", "ig_cookies.txt"
    ),
    "youtube": os.getenv("YT_COOKIES_FILE") or _default_cookie_path(
        "youtube_cookies.txt", "yt_cookies.txt"
    ),
    "pinterest": os.getenv("PIN_COOKIES_FILE") or _default_cookie_path(
        "pinterest_cookies.txt", "pin_cookies.txt"
    ),
    "tiktok": os.getenv("TT_COOKIES_FILE") or _default_cookie_path(
        "tiktok_cookies.txt", "tt_cookies.txt"
    ),
    "twitter": os.getenv("TW_COOKIES_FILE") or _default_cookie_path(
        "twitter_cookies.txt", "tw_cookies.txt", "x_cookies.txt"
    ),
    "soundcloud": os.getenv("SC_COOKIES_FILE") or _default_cookie_path(
        "soundcloud_cookies.txt", "sc_cookies.txt"
    ),
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

URL_RE = re.compile(r"https?://\S+")

# 🩺 Production-hardening (بازبینی کامل دانلودر):
#   - JOB_TIMEOUT_SEC: هر Job حداکثر این‌قدر وقت داره؛ اگه دانلود گیر کرد (نه
#     Exception بده، نه تموم بشه)، به‌جای اینکه برای همیشه یه Thread رو اشغال
#     کنه، با Timeout واضح قطع می‌شه و کاربر پیام روشن می‌گیره.
#   - MAX_TELEGRAM_UPLOAD_BYTES: همون سقفی که تو _base_ydl_opts هم به yt-dlp
#     داده می‌شه؛ برای چک زودهنگام حجم (قبل از شروع دانلود واقعی) هم استفاده می‌شه.
#   - NETWORK_RETRY_DELAYS: فقط برای خطاهای واقعاً موقت (شبکه/Timeout/۵xx) Retry
#     با Backoff انجام می‌شه؛ خطاهای دائمی (Private/Deleted/Invalid) هرگز Retry نمی‌شن.
JOB_TIMEOUT_SEC = 240
MAX_TELEGRAM_UPLOAD_BYTES = 49 * 1024 * 1024
NETWORK_RETRY_DELAYS = (2, 5)

DOWNLOADER_HELP_TEXT = (
    "📥 دانلودر — بنویس «دانلودر»، پلتفرم (اینستاگرام / یوتیوب / تیک‌تاک / ایکس / "
    "پینترست / ساندکلاود) رو با دکمه انتخاب کن، بعد لینک رو همونجا بفرست.\n"
    "حجم فایل همیشه تو کپشن نشون داده می‌شه.\n"
)


def _dl_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(PLATFORM_LABELS["instagram"], callback_data="dl:pick:instagram"),
         InlineKeyboardButton(PLATFORM_LABELS["youtube"], callback_data="dl:pick:youtube")],
        [InlineKeyboardButton(PLATFORM_LABELS["tiktok"], callback_data="dl:pick:tiktok"),
         InlineKeyboardButton(PLATFORM_LABELS["twitter"], callback_data="dl:pick:twitter")],
        [InlineKeyboardButton(PLATFORM_LABELS["pinterest"], callback_data="dl:pick:pinterest"),
         InlineKeyboardButton(PLATFORM_LABELS["soundcloud"], callback_data="dl:pick:soundcloud")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel:main")],
    ])


def _dl_after_pick_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 انتخاب پلتفرم دیگه", callback_data="panel:downloader")],
    ])


# نام عمومی (بدون آندرلاین) که ماژول‌های دیگه (مثلاً bot.py برای پنل اصلی) می‌تونن
# مستقیم importش کنن، بدون اینکه به جزئیات داخلی این ماژول وابسته باشن.
dl_menu_markup = _dl_menu_markup


def _human_size(num_bytes):
    if not num_bytes:
        return "نامشخص"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# =========================================================
#  پینترست — استخراج مستقیم به‌جای yt-dlp
# =========================================================
# روش پینترست تو yt-dlp قدیمیه و اغلب یا هیچی برنمی‌گردونه یا فقط کیفیت پایین.
# این تابع همون تکنیکی رو پیاده می‌کنه که بات‌های اختصاصی پینترست استفاده می‌کنن:
# ۱) اگه لینک کوتاه pin.it باشه، ریدایرکت رو دنبال می‌کنیم تا لینک اصلی pin/<id>
#    به‌دست بیاد.
# ۲) اول resource API خود پینترست (همون APIای که سایتش برای لود کردن پین ازش
#    استفاده می‌کنه) رو صدا می‌زنیم — بهترین کیفیت ویدیو/عکس اورجینال رو می‌ده.
# ۳) اگه جواب نداد، خود صفحه‌ی HTML پین رو می‌گیریم و لینک ویدیو/عکس رو باهاش
#    regex پیدا می‌کنیم.
# اگه هر دو شکست خوردن، کد صدا زننده به yt-dlp به‌عنوان آخرین راه برمی‌گرده.

_PIN_ID_RE = re.compile(r"/pin/(\d+)")


async def _resolve_pinterest_pin_url(url: str, client: httpx.AsyncClient) -> str:
    if "pin.it" in url.lower():
        try:
            resp = await client.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=15)
            return str(resp.url)
        except Exception:
            return url
    return url


async def _pinterest_resource_api(pin_id: str, client: httpx.AsyncClient):
    payload = {"options": {"id": pin_id, "field_set_key": "unauth_react_main_pin"}, "context": {}}
    params = {"data": json.dumps(payload)}
    headers = {
        "User-Agent": USER_AGENT,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*, q=0.01",
        "Referer": "https://www.pinterest.com/",
    }
    resp = await client.get(
        "https://www.pinterest.com/resource/PinResource/get/",
        params=params, headers=headers, timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    pin = (data.get("resource_response") or {}).get("data") or {}
    if not pin:
        return None

    videos = pin.get("videos")
    if videos:
        video_list = (videos.get("video_list") or {})
        if video_list:
            best = max(video_list.values(), key=lambda v: v.get("width", 0))
            return {"url": best["url"], "is_video": True, "title": pin.get("title") or pin.get("grid_title") or ""}

    images = pin.get("images") or {}
    orig = images.get("orig") or {}
    if orig.get("url"):
        return {"url": orig["url"], "is_video": False, "title": pin.get("title") or pin.get("grid_title") or ""}

    return None


async def _pinterest_html_scrape(pin_url: str, client: httpx.AsyncClient):
    resp = await client.get(pin_url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=20)
    resp.raise_for_status()
    html = resp.text

    m = re.search(r'https?:\\/\\/v1\.pinimg\.com\\/videos\\/[^"\\]+\.mp4', html)
    if m:
        return {"url": m.group(0).replace("\\/", "/"), "is_video": True, "title": ""}
    m = re.search(r'https?://v1\.pinimg\.com/videos/[^"\s]+\.mp4', html)
    if m:
        return {"url": m.group(0), "is_video": True, "title": ""}

    m = re.search(r'https?:\\/\\/i\.pinimg\.com\\/originals\\/[^"\\]+\.(?:jpg|jpeg|png|gif)', html)
    if m:
        return {"url": m.group(0).replace("\\/", "/"), "is_video": False, "title": ""}
    m = re.search(r'https?://i\.pinimg\.com/originals/[^"\s]+\.(?:jpg|jpeg|png|gif)', html)
    if m:
        return {"url": m.group(0), "is_video": False, "title": ""}

    return None


async def _pinterest_extract(url: str):
    """امتحان می‌کنه ویدیو/عکس رو مستقیم از پینترست دربیاره. اگه هر دو روش
    شکست خورد، None برمی‌گردونه تا صدا زننده به yt-dlp برگرده."""
    async with httpx.AsyncClient() as client:
        try:
            pin_url = await _resolve_pinterest_pin_url(url, client)
        except Exception:
            pin_url = url

        m = _PIN_ID_RE.search(pin_url)
        if m:
            try:
                result = await _pinterest_resource_api(m.group(1), client)
                if result:
                    return result
            except Exception as e:
                log.info(f"pinterest resource API failed: {e}")

        try:
            result = await _pinterest_html_scrape(pin_url, client)
            if result:
                return result
        except Exception as e:
            log.info(f"pinterest html scrape failed: {e}")

    return None


async def _download_direct_url(media_url: str, outdir: str, is_video: bool, progress_state=None) -> str:
    """استریم مستقیم روی دیسک (نه تو RAM) — با فایل موقت + rename نهایی، تا اگه
    دانلود وسط راه قطع شد، یه فایل ناقص هیچ‌وقت به‌عنوان فایل کامل شناخته نشه."""
    ext = ".mp4" if is_video else (os.path.splitext(media_url.split("?")[0])[1] or ".jpg")
    filepath = os.path.join(outdir, f"pin{ext}")
    tmp_path = filepath + ".part"
    downloaded = 0
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET", media_url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60
            ) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length") or 0) or None
                if progress_state is not None:
                    progress_state["status"] = "downloading"
                    progress_state["total"] = total or 0
                with open(tmp_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=1024 * 64):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_state is not None:
                            progress_state["downloaded"] = downloaded
        if downloaded == 0:
            raise RuntimeError("empty response body (0 bytes downloaded)")
        os.replace(tmp_path, filepath)  # rename نهایی فقط بعد از موفقیت کامل
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise
    if progress_state is not None:
        progress_state["status"] = "processing"
    return filepath


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
        f"{PLATFORM_LABELS[platform]} انتخاب شد ✅\n🔗 حالا لینک رو همینجا بفرست تا برات دانلودش کنم.",
        reply_markup=_dl_after_pick_markup(),
    )
    await q.answer()


_FFMPEG_BIN = shutil.which("ffmpeg")

# 🐛 باگ اصلی که پیدا شد: فرمت "best[ext=mp4]/best" فقط دنبال یه فرمت
# progressive (صدا+تصویر از قبل توی یه فایل) می‌گرده. یوتیوب برای اکثر
# ویدیوهای بالای ۳۶۰p دیگه همچین فرمتی نداره (صدا و تصویر جدا سرو می‌شن)،
# پس این selector یا کیفیت خیلی پایین برمی‌گردوند یا اصلاً هیچ فرمتی پیدا
# نمی‌کرد → دقیقاً همون «یوتیوب اصلاً کار نمی‌کنه». Fix: به yt-dlp اجازه
# می‌دیم بهترین ویدیو + بهترین صدا رو جدا بگیره و با ffmpeg merge کنه
# (merge_output_format=mp4)، با چند سطح Fallback تا هیچ‌وقت درخواست فرمتی
# که اصلاً وجود نداره باعث شکست کامل نشه.
_YOUTUBE_FORMAT = (
    "bestvideo[ext=mp4][filesize<{cap}]+bestaudio[ext=m4a]/"
    "bestvideo+bestaudio/"
    "best[ext=mp4]/best"
).format(cap=MAX_TELEGRAM_UPLOAD_BYTES)

_DEFAULT_FORMAT = "best[ext=mp4]/best"


def _base_ydl_opts(outdir: str, platform: str) -> dict:
    opts = {
        "outtmpl": os.path.join(outdir, "%(id)s.%(ext)s"),
        "format": _YOUTUBE_FORMAT if platform == "youtube" else _DEFAULT_FORMAT,
        "quiet": True,
        "no_warnings": True,
        # noplaylist=True یعنی «فقط یه آیتم رو بگیر، نه کل لیست». برای یوتیوب لازمه
        # (وگرنه لینکِ یه ویدیوی داخل Playlist ممکنه کل Playlist رو دانلود کنه)، ولی
        # همین تنظیم رو اینستاگرام/توییتر باعث می‌شد Carousel (چند عکس/ویدیو تو یه
        # پست) یا چند-مدیای یه توییت فقط اسلاید/مدیای اول دانلود بشه. این‌جا فقط
        # برای instagram/twitter noplaylist رو False می‌ذاریم تا همه‌ی entryهای یه
        # پست/توییت دانلود بشن؛ روی یه پست تک‌مدیا این تنظیم هیچ اثری نداره.
        "noplaylist": platform not in ("instagram", "twitter"),
        "max_filesize": MAX_TELEGRAM_UPLOAD_BYTES,  # سقف آپلود بات‌های تلگرام
        "retries": 3,
        "fragment_retries": 3,
        "http_headers": {"User-Agent": USER_AGENT},
        "geo_bypass": True,
    }
    if platform == "youtube":
        # وقتی صدا/تصویر جدان، باید merge بشن؛ merge بدون ffmpeg خطای واضح می‌ده
        # نه فایل خراب (چون بدون این خط، yt-dlp خودش merge رو سایلنت skip می‌کنه
        # و یه فایل فقط-تصویر یا فقط-صدا می‌مونه که تلگرام یا رد می‌کنه یا صداش قطعه).
        opts["merge_output_format"] = "mp4"
        if _FFMPEG_BIN:
            opts["ffmpeg_location"] = _FFMPEG_BIN
    cookies_file = COOKIES_FILES.get(platform)
    if cookies_file and os.path.exists(cookies_file):
        opts["cookiefile"] = cookies_file
    return opts


_VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".ts")

_FFMPEG_OK = shutil.which("ffmpeg") is not None
_FFPROBE_OK = shutil.which("ffprobe") is not None
if not (_FFMPEG_OK and _FFPROBE_OK):
    log.warning(
        "ffmpeg/ffprobe پیدا نشد — رفع باگ «۰۰:۰۰ و صفحه سیاه» ویدیوهای اینستاگرام "
        "غیرفعال می‌مونه (ویدیو خام و بدون remux فرستاده می‌شه). "
        "روی Railway، nixPkgs = [\"ffmpeg\"] تو nixpacks.toml باید همینو حل کنه."
    )


def _ffprobe_json(filepath: str):
    """بلاک‌کننده‌ست — با asyncio.to_thread صدا زده می‌شه.
    خروجی ffprobe رو به‌صورت dict برمی‌گردونه، یا None اگه فایل اصلاً قابل‌خوندن نبود."""
    if not _FFPROBE_OK:
        return None
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", filepath],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0 or not proc.stdout:
            return None
        return json.loads(proc.stdout)
    except Exception as e:
        log.info(f"ffprobe failed for {filepath}: {e}")
        return None


def _video_meta(probe):
    """duration (float یا None), width, height رو از خروجی ffprobe استخراج می‌کنه."""
    if not probe:
        return None, None, None
    duration = None
    fmt = probe.get("format") or {}
    try:
        duration = float(fmt["duration"]) if fmt.get("duration") else None
    except (TypeError, ValueError):
        duration = None
    width = height = None
    for s in probe.get("streams", []):
        if s.get("codec_type") == "video":
            width, height = s.get("width"), s.get("height")
            if not duration and s.get("duration"):
                try:
                    duration = float(s["duration"])
                except (TypeError, ValueError):
                    pass
            break
    return duration, width, height


def _validate_media_file(filepath: str):
    """بلاک‌کننده — تو asyncio.to_thread صدا زده بشه.

    آیتم ۵ چک‌لیست: هیچ فایلی نباید بدون اعتبارسنجی به تلگرام فرستاده بشه.
    بررسی می‌کنه: فایل وجود داره؟ zero-byte نیست؟ (برای ویدیو/صدا) ffprobe
    stream سالم پیدا می‌کنه؟ خروجی: (ok: bool, دلیل_فارسی_یا_None)."""
    if not filepath or not os.path.exists(filepath):
        return False, "فایل خروجی روی دیسک پیدا نشد."
    size = os.path.getsize(filepath)
    if size == 0:
        return False, "فایل خروجی صفر بایت است (دانلود ناقص)."
    ext = os.path.splitext(filepath)[1].lower()
    is_av = ext in _VIDEO_EXTS or ext in (".mp3", ".m4a", ".opus", ".ogg", ".wav")
    if is_av and _FFPROBE_OK:
        probe = _ffprobe_json(filepath)
        if probe is None:
            return False, "container فایل توسط ffprobe قابل‌خواندن نیست."
        streams = probe.get("streams", [])
        if not streams:
            return False, "هیچ stream صوتی/تصویری در فایل پیدا نشد."
        if ext in _VIDEO_EXTS and not any(s.get("codec_type") == "video" for s in streams):
            return False, "فایل ویدیویی فاقد stream تصویری است."
    return True, None


def _remux_faststart(filepath: str):
    """بلاک‌کننده‌ست. Remux سریع (بدون Re-encode، فقط -c copy) با +faststart تا
    moov atom بیاد اول فایل و duration/metadata درست تشخیص داده بشه. اگه موفق
    نشد None برمی‌گردونه (نه Exception) تا فراخوان بره سراغ Re-encode."""
    if not _FFMPEG_OK:
        return None
    base, _ = os.path.splitext(filepath)
    out_path = base + "_fx.mp4"
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", filepath, "-c", "copy", "-movflags", "+faststart", out_path],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception as e:
        log.info(f"faststart remux failed for {filepath}: {e}")
    if os.path.exists(out_path):
        try:
            os.remove(out_path)
        except Exception:
            pass
    return None


def _reencode_video(filepath: str):
    """بلاک‌کننده‌ست. فقط وقتی صدا زده می‌شه که remux ساده کافی نبوده (نادر —
    مثلاً استریم‌های ناجور/خراب منبع). کیفیت رو تا حد امکان حفظ می‌کنه
    (CRF ثابت به‌جای بیت‌ریت پایین‌ی ثابت) تا حجم و کیفیت بی‌دلیل بد نشه."""
    if not _FFMPEG_OK:
        return None
    base, _ = os.path.splitext(filepath)
    out_path = base + "_enc.mp4"
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", filepath,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
             "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart", out_path],
            capture_output=True, text=True, timeout=300,
        )
        if proc.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception as e:
        log.info(f"re-encode fallback failed for {filepath}: {e}")
    return None


def _fix_video_for_telegram(filepath: str):
    """بلاک‌کننده‌ست — حتماً باید تو asyncio.to_thread صدا زده بشه.

    مشکل: بعضی ویدیوهای دانلودی (مخصوصاً از اینستاگرام، ویدیوهای نسبتاً طولانی)
    moov atom‌شون آخر فایل‌ه یا duration/metadata‌شون کامل نیست؛ تلگرام قبل از
    کامل شدن دانلودِ کاربر، پلیر رو با 00:00 و صفحه‌ی سیاه نشون می‌ده.

    راه‌حل: اول یه Remux سریع و بدون افت کیفیت (-c copy) با +faststart امتحان
    می‌کنیم (تقریباً رایگان از نظر CPU). فقط اگه بعد از remux هم duration درست
    تشخیص داده نشد (یعنی خودِ remux کافی نبود)، می‌ریم سراغ Re-encode واقعی —
    نه به‌صورت پیش‌فرض برای همه‌ی ویدیوها.

    خروجی: (مسیر_نهایی_فایل, duration_یا_None, width_یا_None, height_یا_None)
    """
    probe = _ffprobe_json(filepath)
    duration, width, height = _video_meta(probe)

    if probe is None:
        # فایل با ffprobe اصلاً قابل‌خوندن نبود (یا ffprobe نصب نیست) — همون فایل
        # خام رو برمی‌گردونیم؛ بهتره تلگرام خودش امتحان کنه تا اصلاً نفرستیم.
        return filepath, None, None, None

    remuxed = _remux_faststart(filepath)
    if remuxed:
        d2, w2, h2 = _video_meta(_ffprobe_json(remuxed))
        if d2:
            return remuxed, d2, w2, h2
        try:
            os.remove(remuxed)
        except Exception:
            pass

    reencoded = _reencode_video(filepath)
    if reencoded:
        d3, w3, h3 = _video_meta(_ffprobe_json(reencoded))
        return reencoded, d3, w3, h3

    # نه remux و نه re-encode جواب نداد — فایل اصلی رو با هر متادیتایی که از اول
    # پیدا شده بود می‌فرستیم؛ حداقل چیزی که فرستادیم می‌شه بهتر از هیچی نیست.
    return filepath, duration, width, height


def _yt_dlp_download(url: str, outdir: str, platform: str, progress_state=None):
    """بلاک‌کننده‌ست — حتماً باید تو asyncio.to_thread صدا زده بشه.

    برای یوتیوب چند تا player_client رو پشت‌سرهم امتحان می‌کنیم، چون بعضی‌هاشون
    (مثل android/ios) گاهی قفل «Sign in to confirm you're not a bot» رو دور
    می‌زنن حتی بدون کوکی، ولی تضمینی نیست — اگه یوتیوب واقعاً لینک رو قفل کرده
    باشه، تنها راه قطعی فایل کوکیِ یه اکانت لاگین‌شده‌ست (YT_COOKIES_FILE).
    آخرین تلاش هیچ extractor_args ای نمی‌ذاره (رفتار پیش‌فرض خودِ yt-dlp، که
    خودش داخلی بین clientها و PO-token هماهنگ می‌کنه) — چون قفل کردن به سه
    client ثابت باعث می‌شد اگه هر سه با نسخه‌ی نصب‌شده‌ی yt-dlp ناسازگار بودن،
    دانلود کلاً شکست بخوره بدون این‌که راه‌حل پیش‌فرض/جدیدتر امتحان بشه.
    """
    base = _base_ydl_opts(outdir, platform)
    attempts = [{}]
    if platform == "youtube":
        attempts = [
            {"extractor_args": {"youtube": {"player_client": ["android", "web"]}}},
            {"extractor_args": {"youtube": {"player_client": ["ios"]}}},
            {},  # پیش‌فرض کامل yt-dlp، بدون هیچ محدودیت client
        ]
    if platform == "soundcloud":
        # ساندکلاود صوتیه؛ فرمت ویدیویی معنی نداره، بهترین فایل صوتی رو می‌گیریم
        base = {**base, "format": "bestaudio/best"}

    def _hook(d):
        if progress_state is None:
            return
        try:
            if d.get("status") == "downloading":
                progress_state["status"] = "downloading"
                progress_state["downloaded"] = d.get("downloaded_bytes") or 0
                progress_state["total"] = (
                    d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                )
                progress_state["speed"] = d.get("speed") or 0
                progress_state["eta"] = d.get("eta")
            elif d.get("status") == "finished":
                progress_state["status"] = "processing"
        except Exception:
            pass

    last_err = None
    for extra in attempts:
        opts = {**base, **extra, "progress_hooks": [_hook]}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                # وقتی merge اتفاق افتاده (صدا+تصویر جدا بودن)، پسوند خروجی نهایی
                # طبق merge_output_format عوض می‌شه؛ prepare_filename گاهی پسوند
                # منبع رو برمی‌گردونه نه پسوند merge‌شده — این‌جا تصحیحش می‌کنیم.
                if opts.get("merge_output_format") and not os.path.exists(filepath):
                    alt = os.path.splitext(filepath)[0] + "." + opts["merge_output_format"]
                    if os.path.exists(alt):
                        filepath = alt
            return filepath, info
        except Exception as e:
            last_err = e
            continue
    raise last_err


def _yt_dlp_probe(url: str, platform: str):
    """بلاک‌کننده — باید تو asyncio.to_thread صدا زده بشه. فقط Metadata (عنوان/
    مدت/حجم تقریبی) رو بدون دانلود واقعی می‌گیره (download=False)، تا قبل از
    شروع دانلود واقعی بشه به کاربر نشون داد. اگه شکست خورد، None برمی‌گردونه —
    این یه مسیر Best-effort‌ه و نباید جلوی دانلود اصلی رو بگیره."""
    if yt_dlp is None:
        return None
    opts = {**_base_ydl_opts(tempfile.gettempdir(), platform), "skip_download": True}
    opts.pop("max_filesize", None)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        log.info(f"metadata probe failed for {platform} ({url}): {e}")
        return None


def _log_job(job_id: str, **fields):
    """لاگ ساخت‌یافته‌ی هر مرحله‌ی یه Job دانلود — platform/url/user_id/job_id/
    output path/file size/duration/exit status و... طبق چک‌لیست موردنیاز، ولی
    هیچ‌وقت این جزئیات مستقیم به کاربر نشون داده نمی‌شه، فقط تو Log می‌مونه."""
    parts = " ".join(f"{k}={v!r}" for k, v in fields.items())
    log.info(f"[dl:{job_id}] {parts}")


def _classify_download_error(err_text: str):
    """متن خام Exception (yt-dlp/httpx) رو به یه پیام فارسیِ دقیق و بدون جزئیات
    فنی تبدیل می‌کنه، به‌علاوه‌ی این‌که آیا این خطا موقتیه و ارزش Retry داره.
    هیچ‌وقت به‌جای این‌ها پیام عمومی «فایل پیدا نشد» برنمی‌گردونه — طبق قانون
    اصلی دانلودر، هر خطا باید علت واقعی خودش رو نشون بده."""
    t = (err_text or "").lower()

    if "sign in to confirm" in t or "not a bot" in t:
        return (
            "🔐 نیاز به ورود/احراز هویت — یوتیوب این لینک رو پشت قفل ضد-ربات "
            "گذاشته و بدون کوکیِ یه اکانت لاگین‌شده قابل دانلود نیست.",
            False,
        )
    if "empty media response" in t or ("login" in t and "instagram" in t):
        return ("🔒 محتوای خصوصی است یا پلتفرم بدون لاگین اجازه‌ی دسترسی نمی‌ده.", False)
    if "private video" in t or "private account" in t or "this profile is private" in t:
        return ("🔒 محتوای خصوصی است.", False)
    if ("video unavailable" in t or "has been removed" in t or "no longer available" in t
            or "content isn't available" in t or "post unavailable" in t):
        return ("🚫 محتوا حذف شده یا در دسترس نیست.", False)
    if "not available in your country" in t or ("geo" in t and "restrict" in t):
        return ("🌍 این محتوا در منطقه‌ی سرور ربات قابل دسترسی نیست.", False)
    if "requires authentication" in t or "join this channel" in t or "subscribers only" in t:
        return ("🔐 این محتوا نیاز به ورود/احراز هویت یا عضویت ویژه داره.", False)
    if "max_filesize" in t or "max-filesize" in t or "file is larger than" in t:
        return ("📦 حجم فایل بیشتر از محدودیت مجاز ارسال است.", False)
    if ("unsupported url" in t or "no video formats found" in t
            or "requested format is not available" in t or "no formats found" in t):
        return ("⚠️ فرمت این رسانه توسط ربات پشتیبانی نمی‌شود.", False)
    if "invalid url" in t or "is not a valid url" in t or "unable to extract" in t:
        return ("⚠️ لینک نامعتبر است یا محتوایی داخلش پیدا نشد.", False)
    if "403" in t or "forbidden" in t:
        return ("🛑 دانلود توسط پلتفرم مسدود شد.", False)
    if any(k in t for k in (
        "connecterror", "connect error", "connection reset", "temporary failure",
        "name or service not known", "network is unreachable", "connectionerror",
    )):
        return ("🌐 خطای شبکه هنگام دانلود پیش اومد.", True)
    if "timed out" in t or "timeout" in t:
        return ("⏱ زمان دانلود تمام شد.", True)
    if any(k in t for k in ("502", "503", "504", "server error", "internal error")):
        return ("⚙️ خطای موقت سرویس؛ کمی دیگه دوباره امتحان کن.", True)

    return ("❌ خطای نامشخص در دانلود؛ جزئیاتش تو لاگ ربات ثبت شد.", False)


async def _download_with_retry(url: str, tmpdir: str, platform: str, job_id: str, progress_state=None):
    """دور _yt_dlp_download رو با Timeout و Retry-با-Backoff (فقط برای خطاهای
    موقت) می‌پیچه. خطاهای دائمی (Private/Deleted/Invalid/...) بدون تلف‌کردن وقت
    فوراً بالا پرتاب می‌شن."""
    attempt = 0
    while True:
        attempt += 1
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_yt_dlp_download, url, tmpdir, platform, progress_state),
                timeout=JOB_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            _log_job(job_id, platform=platform, url=url, stage="timeout", attempt=attempt)
            raise
        except Exception as e:
            _, retryable = _classify_download_error(str(e))
            if retryable and attempt <= len(NETWORK_RETRY_DELAYS):
                delay = NETWORK_RETRY_DELAYS[attempt - 1]
                _log_job(job_id, platform=platform, url=url, stage="retry",
                          attempt=attempt, delay=delay, error=str(e)[:200])
                await asyncio.sleep(delay)
                continue
            raise


# 🩺 رفع باگ «تایمر/حجم روی 00:00 و اطلاعات اشتباه گیر می‌کنه»: قبلاً پیام
# وضعیت فقط یه‌بار قبل از دانلود ست می‌شد و تا پایان کار دیگه هیچ‌وقت آپدیت
# نمی‌شد — یعنی در طول کل دانلود (که ممکنه چند ده ثانیه طول بکشه) کاربر همون
# پیام اولیه‌ی ثابت رو می‌دید. این تابع هر ۱.۵ ثانیه (نه هر chunk — طبق قانون
# ضدکندی/race condition) پیام رو با درصد/حجم/سرعت/ETA واقعیِ progress_state
# (که از progress_hooks یوتیوب/ساندکلاود یا از _download_direct_url پینترست پر
# می‌شه) آپدیت می‌کنه. تا وقتی metadata واقعی نیومده، صریحاً «در حال دریافت
# اطلاعات...» نشون می‌ده — هیچ‌وقت 00:00 یا حجم جعلی نمی‌سازه.
async def _progress_ticker(status_msg, progress_state: dict, header: str, stop_event: asyncio.Event):
    last_text = None
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=1.5)
            break  # stop_event ست شد
        except asyncio.TimeoutError:
            pass  # وقت tick رسید، ادامه بده و یه‌بار دیگه آپدیت کن

        status = progress_state.get("status")
        lines = [header]
        if status == "downloading" and progress_state.get("total"):
            downloaded = progress_state.get("downloaded", 0)
            total = progress_state["total"]
            pct = min(100, downloaded / total * 100) if total else 0
            lines.append("⬇️ در حال دانلود...")
            lines.append(f"📦 حجم: {_human_size(downloaded)} / {_human_size(total)}")
            lines.append(f"📊 پیشرفت: {pct:.0f}%")
            speed = progress_state.get("speed")
            if speed:
                lines.append(f"⚡ سرعت: {_human_size(speed)}/s")
            eta = progress_state.get("eta")
            if eta is not None:
                m, s = divmod(int(eta), 60)
                lines.append(f"⏱ زمان باقی‌مانده: {m:02d}:{s:02d}")
        elif status == "downloading":
            lines.append("⬇️ در حال دانلود...")
            lines.append("📦 در حال دریافت اطلاعات حجم...")
        elif status == "processing":
            lines.append("⚙️ در حال پردازش نهایی فایل...")
        else:
            lines.append("⏳ در حال دریافت اطلاعات...")

        text = "\n".join(lines)
        if text != last_text:
            try:
                await status_msg.edit_text(text)
                last_text = text
            except Exception:
                pass  # (مثلاً "message not modified") — بی‌اهمیت، tick بعدی درستش می‌کنه


async def downloader_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    text = (msg.text or "").strip()

    match = URL_RE.search(text)
    if not match:
        return  # این پیام لینک نیست، به بقیه‌ی هندلرها بسپار

    url = match.group(0)
    # 🆔 هر درخواست یه Job ID مستقل داره — فقط برای رهگیری تو Logها (چک‌لیست
    # Persistence/Debug)، نه برای مسیر فایل (اون یه TemporaryDirectory جدا و
    # منحصربه‌فرده که خودِ tempfile می‌سازه، پس هر دانلود کاملاً مستقله).
    job_id = uuid.uuid4().hex[:10]

    # 🔧 رفع باگ Downloader داخل Group/Private: قبلاً این هندلر فقط وقتی کار
    # می‌کرد که کاربر اول «دانلودر» رو می‌زد و از منو پلتفرم رو دستی انتخاب
    # می‌کرد (PENDING_DL). اگه کاربر مستقیم لینک می‌فرستاد (دقیقاً کاری که تو
    # گروه انجام می‌شه)، uid تو PENDING_DL نبود و کل پیام بی‌صدا نادیده گرفته
    # می‌شد — چه تو گروه، چه تو پیوی. حالا اگه پلتفرم از قبل انتخاب نشده باشه،
    # از روی خودِ دامنه‌ی لینک تشخیص داده می‌شه تا نیازی به مرحله‌ی انتخاب منو
    # نباشه؛ اگه از قبل انتخاب شده باشه (PENDING_DL)، همون رفتار قبلی (با چک
    # تطبیق دامنه) دست‌نخورده می‌مونه.
    if uid in PENDING_DL:
        platform = PENDING_DL.pop(uid)
        allowed_domains = PLATFORM_DOMAINS[platform]
        if not any(d in url.lower() for d in allowed_domains):
            await msg.reply_text(
                f"⚠️ این لینک برای {PLATFORM_LABELS[platform]} نیست. دوباره «دانلودر» رو بزن و پلتفرم درست رو انتخاب کن."
            )
            return
    else:
        platform = _detect_platform_from_url(url)
        if platform is None:
            return  # لینک به هیچ‌کدوم از پلتفرم‌های پشتیبانی‌شده نمی‌خوره؛ به بقیه‌ی هندلرها سپرده می‌شه

    _log_job(job_id, platform=platform, url=url, user_id=uid, chat_id=chat_id, stage="start")

    # برای پینترست به yt-dlp نیازی نیست (روش مستقیم پایین‌تر کارو انجام می‌ده)،
    # فقط برای یوتیوب/اینستاگرام (و fallback خود پینترست) لازمه.
    if yt_dlp is None and platform != "pinterest":
        await msg.reply_text("⚠️ ماژول دانلود نصب نشده. باید yt-dlp تو requirements.txt باشه (اضافه شده، فقط دیپلوی دوباره لازمه).")
        return

    # ⚠️ لینک Playlist کاملِ یوتیوب (نه یه ویدیوی مشخص، نه Shorts) رو عمداً رد
    # می‌کنیم به‌جای این‌که بی‌صدا فقط یه ویدیوی اول رو بفرستیم — طبق قانون
    # «هیچ خطایی نباید با پیام گمراه‌کننده پوشونده بشه»، سکوت هم همون‌قدر
    # گمراه‌کننده‌ست.
    if platform == "youtube" and "list=" in url.lower() and "v=" not in url.lower() and "youtu.be" not in url.lower() and "/shorts/" not in url.lower():
        await msg.reply_text(
            "⚠️ این یه لینک Playlist کامل یوتیوبه. برای جلوگیری از دانلود ناخواسته‌ی حجم زیاد، فعلاً "
            "فقط دانلود تک‌ویدیو/Shorts پشتیبانی می‌شه — لینک مستقیم همون ویدیویی که می‌خوای رو بفرست."
        )
        return

    status = await msg.reply_text(f"⏳ در حال دانلود از {PLATFORM_LABELS[platform]}...")

    # 📊 پیش‌نمایش Metadata (عنوان/مدت/حجم تقریبی) قبل از شروع دانلود واقعی —
    # فقط برای یوتیوب/ساندکلاود که extract_info(download=False) سریع و قابل‌اتکاست.
    # Best-effort‌ه: اگه شکست خورد یا طول کشید، بی‌سروصدا رد می‌شیم سراغ دانلود اصلی.
    if platform in ("youtube", "soundcloud") and yt_dlp is not None:
        try:
            probe_info = await asyncio.wait_for(
                asyncio.to_thread(_yt_dlp_probe, url, platform), timeout=15
            )
        except Exception:
            probe_info = None
        if probe_info:
            approx_bytes = probe_info.get("filesize") or probe_info.get("filesize_approx")
            if approx_bytes and approx_bytes > MAX_TELEGRAM_UPLOAD_BYTES:
                _log_job(job_id, platform=platform, url=url, stage="pre-check-filesize-reject",
                          approx_bytes=approx_bytes)
                await status.edit_text(
                    "❌ دانلود انجام نشد\nعلت: 📦 حجم فایل برای ارسال مستقیم توسط ربات بیش از حد مجاز است."
                )
                return
            title = (probe_info.get("title") or "").strip()
            duration_s = probe_info.get("duration")
            lines = ["▶️ YouTube" if platform == "youtube" else "🎧 SoundCloud"]
            if title:
                lines.append(f"{'🎬 عنوان' if platform == 'youtube' else '🎵 Track'}: {title}")
            if duration_s:
                m, s = divmod(int(duration_s), 60)
                lines.append(f"⏱ مدت: {m:02d}:{s:02d}")
            lines.append(f"📦 حجم تقریبی: {_human_size(approx_bytes)}" if approx_bytes else "📦 حجم: در حال محاسبه...")
            lines.append("")
            lines.append("⏳ در حال دانلود...")
            try:
                await status.edit_text("\n".join(lines))
            except Exception:
                pass

    with tempfile.TemporaryDirectory() as tmpdir:
        # پینترست: اول روش مستقیم (resource API / اسکرپ HTML) رو امتحان کن،
        # چون خیلی سریع‌تر و مطمئن‌تر از yt-dlp برای این پلتفرمه. فقط اگه
        # شکست خورد میره سراغ yt-dlp (مسیر قدیمی، پایین همین تابع).
        if platform == "pinterest":
            try:
                media = await _pinterest_extract(url)
            except Exception as e:
                log.info(f"[dl:{job_id}] pinterest direct extract error: {e}")
                media = None
            if media:
                # 🐛 باگ پیدا‌شده: این مسیر (روش مستقیم Pinterest) فایل رو مستقیم
                # می‌فرستاد بدون هیچ progress، بدون ffprobe validation و بدون
                # remux/faststart fix — دقیقاً همون مسیری که کاربر می‌گفت
                # «Preview سیاه می‌شه / تایمر 00:00 می‌مونه». الان همون validation
                # + fix + progress واقعی که برای مسیر yt-dlp هست، این‌جا هم اجرا می‌شه.
                progress_state = {"status": "downloading", "total": 0, "downloaded": 0}
                stop_event = asyncio.Event()
                ticker = asyncio.create_task(
                    _progress_ticker(status, progress_state, "📌 Pinterest", stop_event)
                )
                try:
                    filepath = await _download_direct_url(
                        media["url"], tmpdir, media["is_video"], progress_state
                    )
                except Exception as e:
                    stop_event.set()
                    try:
                        await ticker
                    except Exception:
                        pass
                    log.info(f"[dl:{job_id}] pinterest direct download failed, falling back to yt-dlp: {e}")
                    filepath = None
                else:
                    stop_event.set()
                    try:
                        await ticker
                    except Exception:
                        pass

                if filepath:
                    caption = media.get("title") or None
                    send_path = filepath
                    v_duration = v_width = v_height = None
                    if media["is_video"]:
                        try:
                            send_path, v_duration, v_width, v_height = await asyncio.to_thread(
                                _fix_video_for_telegram, filepath
                            )
                        except Exception as e:
                            log.warning(f"[dl:{job_id}] pinterest video fixup failed: {e}")
                            send_path = filepath
                    ok, reason = await asyncio.to_thread(_validate_media_file, send_path)
                    if not ok:
                        log.error(f"[dl:{job_id}] pinterest output failed validation: {reason} path={send_path!r}")
                        await status.edit_text(f"❌ دانلود انجام نشد\nعلت: 🩹 فایل دریافتی خراب بود ({reason})")
                        return
                    try:
                        with open(send_path, "rb") as f:
                            if media["is_video"]:
                                await msg.reply_video(
                                    f, caption=caption, supports_streaming=True,
                                    duration=int(v_duration) if v_duration else None,
                                    width=v_width or None, height=v_height or None,
                                )
                            else:
                                await msg.reply_photo(f, caption=caption)
                        _log_job(job_id, platform=platform, url=url, stage="sent",
                                  output_path=send_path, file_size=os.path.getsize(send_path))
                        try:
                            await status.delete()
                        except Exception:
                            pass
                        return
                    except Exception as e:
                        log.warning(f"[dl:{job_id}] pinterest send failed: {e}")
                        await status.edit_text(
                            "❌ ارسال فایل انجام نشد\nعلت: 📦 حجم فایل بیشتر از محدودیت مجاز است یا تلگرام موقتاً پاسخ نداد."
                        )
                        return
            if yt_dlp is None:
                await status.edit_text(
                    "❌ دانلود انجام نشد\nعلت: دانلود مستقیم از پینترست شکست خورد و yt-dlp هم نصب نیست تا Fallback بشه."
                )
                return

        header = {
            "youtube": "▶️ YouTube", "instagram": "📸 Instagram", "pinterest": "📌 Pinterest",
            "tiktok": "🎵 TikTok", "twitter": "🐦 X/Twitter", "soundcloud": "🎧 SoundCloud",
        }.get(platform, PLATFORM_LABELS.get(platform, ""))
        progress_state = {"status": "downloading", "total": 0, "downloaded": 0}
        stop_event = asyncio.Event()
        ticker = asyncio.create_task(_progress_ticker(status, progress_state, header, stop_event))

        start_ts = time.monotonic()
        try:
            filepath, info = await _download_with_retry(url, tmpdir, platform, job_id, progress_state)
        except asyncio.TimeoutError:
            log.warning(f"[dl:{job_id}] timeout platform={platform} url={url} user_id={uid} "
                        f"after={time.monotonic() - start_ts:.1f}s")
            stop_event.set()
            try:
                await ticker
            except Exception:
                pass
            await status.edit_text("❌ دانلود انجام نشد\nعلت: ⏱ زمان دانلود تمام شد.")
            return
        except Exception as e:
            # Traceback کامل فقط تو Log — هرگز به کاربر نشون داده نمی‌شه.
            log.exception(f"[dl:{job_id}] download failed platform={platform} url={url} user_id={uid}")
            stop_event.set()
            try:
                await ticker
            except Exception:
                pass
            reason, _ = _classify_download_error(str(e))
            await status.edit_text(f"❌ دانلود انجام نشد\nعلت: {reason}")
            return
        finally:
            stop_event.set()

        try:
            await ticker
        except Exception:
            pass

        download_duration = time.monotonic() - start_ts

        # 🃏 Carousel / چند-مدیای اینستاگرام و توییتر: اگه yt-dlp چند entry
        # برگردونده (noplaylist=False برای این دو پلتفرم، بالاتر تو _base_ydl_opts)،
        # مسیر واقعیِ هر entry رو با prepare_filename خودِ yt-dlp پیدا می‌کنیم —
        # نه Glob و نه حدسِ اسم فایل. اگه entry نبود، مسیر قدیمیِ تک‌فایل زیر
        # دست‌نخورده اجرا می‌شه.
        entries = info.get("entries") if isinstance(info, dict) else None
        if entries and platform in ("instagram", "twitter"):
            media_files = []
            try:
                with yt_dlp.YoutubeDL(_base_ydl_opts(tmpdir, platform)) as ydl2:
                    for entry in entries:
                        if not entry:
                            continue
                        try:
                            epath = ydl2.prepare_filename(entry)
                        except Exception:
                            continue
                        if epath and os.path.exists(epath):
                            media_files.append(epath)
            except Exception as e:
                log.info(f"[dl:{job_id}] carousel entry resolution failed: {e}")
                media_files = []

            if len(media_files) > 1:
                _log_job(job_id, platform=platform, url=url, stage="carousel", count=len(media_files))
                await status.edit_text(f"📦 {len(media_files)} فایل پیدا شد\n⚡ در حال پردازش و ارسال...")
                group = []
                opened = []
                try:
                    for epath in media_files[:10]:  # سقف Media Group تلگرام = ۱۰
                        eext = os.path.splitext(epath)[1].lower()
                        send_epath = epath
                        # 🐛 همون باگ «صفحه سیاه» تو مسیر Carousel هم وجود داشت:
                        # این‌جا هم قبلاً هیچ remux/faststart fix و هیچ validation
                        # اجرا نمی‌شد، برخلاف مسیر تک‌فایل زیر که داشت. الان یکسان شد.
                        if eext in _VIDEO_EXTS:
                            try:
                                send_epath, _, _, _ = await asyncio.to_thread(_fix_video_for_telegram, epath)
                            except Exception as e:
                                log.warning(f"[dl:{job_id}] carousel entry fixup failed: {e}")
                                send_epath = epath
                        ok, reason = await asyncio.to_thread(_validate_media_file, send_epath)
                        if not ok:
                            log.warning(f"[dl:{job_id}] carousel entry skipped, invalid: {reason} path={send_epath!r}")
                            continue  # آیتم خراب رد می‌شه، بقیه‌ی گالری ارسال می‌شه
                        f = open(send_epath, "rb")
                        opened.append(f)
                        if eext in (".jpg", ".jpeg", ".png", ".webp"):
                            group.append(InputMediaPhoto(f))
                        else:
                            group.append(InputMediaVideo(f, supports_streaming=True))
                    if not group:
                        await status.edit_text(
                            "❌ ارسال انجام نشد\nعلت: 🩹 هیچ‌کدام از فایل‌های این پست معتبر/سالم نبودند."
                        )
                        return
                    await msg.reply_media_group(media=group)
                    _log_job(job_id, platform=platform, url=url, stage="sent",
                              count=len(group), download_duration=round(download_duration, 1))
                finally:
                    for f in opened:
                        try:
                            f.close()
                        except Exception:
                            pass
                try:
                    await status.delete()
                except Exception:
                    pass
                return
            elif len(media_files) == 1:
                # فقط یه entry معتبر Resolve شد — همون رو به‌جای مسیر سطح‌بالا
                # (که برای دیکشنری‌های نوع Playlist ممکنه معتبر نباشه) به‌عنوان
                # filepath واقعی استفاده می‌کنیم و با همون منطق تک‌فایلِ زیر ادامه می‌دیم.
                filepath = media_files[0]
            # اگه اصلاً entry معتبری Resolve نشد، از همین‌جا با filepath سطح‌بالای
            # قبلی ادامه می‌دیم؛ اگه اونم نامعتبر باشه، چک زیر (Output Missing)
            # با پیام صادقانه (نه «فایل پیدا نشد») گزارشش می‌ده.

        if not filepath or not os.path.exists(filepath):
            # 🧠 دقیقاً همون چیزی که نباید بشه: هیچ‌وقت «فایل پیدا نشد» ساده به
            # کاربر نشون داده نمی‌شه. اینجا Debug کامل تو Log ثبت می‌شه (لیست
            # واقعیِ پوشه‌ی Job + کلیدهای info) تا علت واقعی قابل‌ردیابی باشه،
            # و به کاربر یه علت مشخص (نه یه پیام عمومی گمراه‌کننده) داده می‌شه.
            try:
                tmp_listing = os.listdir(tmpdir)
            except Exception:
                tmp_listing = "N/A"
            log.error(
                f"[dl:{job_id}] output missing platform={platform} url={url} user_id={uid} "
                f"expected_path={filepath!r} tmpdir_listing={tmp_listing!r} "
                f"info_keys={sorted(info.keys()) if isinstance(info, dict) else 'N/A'}"
            )
            await status.edit_text(
                "❌ دانلود انجام نشد\nعلت: پلتفرم فایل خروجی معتبری برنگردوند — معمولاً یعنی فرمت "
                "این پست/رسانه توسط ربات پشتیبانی نمی‌شه."
            )
            return

        real_size = os.path.getsize(filepath)
        mime_type, _ = mimetypes.guess_type(filepath)
        title = (info.get("title") or "").strip()
        size_line = f"📦 حجم: {_human_size(real_size)}"
        caption = f"{title}\n{size_line}" if title else size_line

        _log_job(
            job_id, platform=platform, url=url, user_id=uid, chat_id=chat_id,
            output_path=filepath, file_size=real_size, mime_type=mime_type,
            download_duration=round(download_duration, 1), extractor=info.get("extractor"),
            selected_format=info.get("format_id"), stage="downloaded",
        )

        ext = os.path.splitext(filepath)[1].lower()
        send_path = filepath
        v_duration = v_width = v_height = None
        if ext in _VIDEO_EXTS and platform != "soundcloud":
            # رفع باگ «۰۰:۰۰ / صفحه سیاه»: قبل از ارسال، duration و metadata رو
            # با ffprobe چک و در صورت نیاز با ffmpeg (remux سریع، نه لزوماً
            # re-encode) درست می‌کنیم. این کار تو ترد جدا انجام می‌شه تا event
            # loop ربات قفل نشه.
            try:
                send_path, v_duration, v_width, v_height = await asyncio.to_thread(
                    _fix_video_for_telegram, filepath
                )
            except Exception as e:
                log.warning(f"[dl:{job_id}] video fixup failed, sending raw file: {e}")
                send_path = filepath

        # ✅ آیتم ۵ چک‌لیست: قبل از ارسال، فایل نهایی حتماً اعتبارسنجی می‌شه —
        # نه zero-byte، نه container خراب، نه فقط‌صدا/فقط‌تصویر ناقص.
        ok, reason = await asyncio.to_thread(_validate_media_file, send_path)
        if not ok:
            log.error(f"[dl:{job_id}] final output failed validation: {reason} path={send_path!r}")
            await status.edit_text(f"❌ دانلود انجام نشد\nعلت: 🩹 فایل دریافتی سالم نبود ({reason})")
            return
        try:
            with open(send_path, "rb") as f:
                if ext in (".jpg", ".jpeg", ".png", ".webp"):
                    await msg.reply_photo(f, caption=caption or None)
                elif platform == "soundcloud" or ext in (".mp3", ".m4a", ".opus", ".ogg", ".wav"):
                    await msg.reply_audio(f, caption=caption or None, title=title or None)
                else:
                    await msg.reply_video(
                        f, caption=caption or None, supports_streaming=True,
                        duration=int(v_duration) if v_duration else None,
                        width=v_width or None, height=v_height or None,
                    )
            _log_job(job_id, platform=platform, url=url, stage="sent")
        except Exception as e:
            log.warning(f"[dl:{job_id}] send failed, fallback to document: {e}")
            try:
                with open(filepath, "rb") as f:
                    await msg.reply_document(f, caption=caption or None)
                _log_job(job_id, platform=platform, url=url, stage="sent-as-document")
            except Exception as e2:
                log.exception(f"[dl:{job_id}] document fallback also failed")
                await status.edit_text(
                    "❌ ارسال فایل انجام نشد\nعلت: 📦 حجم فایل بیشتر از محدودیت مجاز است یا تلگرام "
                    "موقتاً پاسخ نداد."
                )
                return

        # 🧹 Cleanup: فقط بعد از ارسال موفق فایل حذف می‌شه؛ چون فایل داخل
        # TemporaryDirectory هست، خروج از بلوک with همین‌جا کل پوشه‌ی Job رو
        # (فایل خام + فایل‌های remux/re-encode احتمالی) پاک می‌کنه — نه زودتر.
        try:
            await status.delete()
        except Exception:
            pass


def register_downloader(app):
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^\s*(دانلودر|دانلود)\s*$"), downloader_menu), group=6)
    app.add_handler(CallbackQueryHandler(downloader_pick_callback, pattern=r"^dl:pick:"), group=6)
    # این هندلر با هر پیام متنی چک می‌کنه که آیا لینک‌شده و منتظرشیم؛ وگرنه هیچ کاری نمی‌کنه
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader_link_handler), group=6)
