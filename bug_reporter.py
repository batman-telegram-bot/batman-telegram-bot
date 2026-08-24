# -*- coding: utf-8 -*-
"""Gotham Bot - centralized error reporter.
Sends concise diagnostics to OWNER_ID and keeps a small in-memory recent-error list.
Never includes API keys or Authorization headers.
"""
import os
import traceback
from collections import deque
from datetime import datetime, timezone

from telegram import Bot

RECENT_ERRORS = deque(maxlen=20)

# دسته‌بندی خطاها طبق مشخصات (Exception/API/Handler/Database/AI/Downloader).
# چون فیلد kind یه رشته‌ی آزاده (هر فراخوانی remember_error هرچی بخواد می‌ده)،
# دسته‌بندی با تطبیق کلیدواژه رو خودِ همون داده‌ی واقعی انجام می‌شه — چیزی
# جعل نمی‌شه، فقط داده‌ی موجود مرتب می‌شه.
BUG_CATEGORIES = {
    "api": ("API", ("api", "groq", "http", "download", "yt-dlp", "instaloader")),
    "handler": ("Handler", ("handler", "callback", "button", "keyboard")),
    "database": ("Database", ("db", "database", "sqlite", "sql")),
    "ai": ("AI", ("ai", "groq", "llm", "voice", "transcribe", "recognition")),
    "downloader": ("Downloader", ("downloader", "youtube", "instagram", "tiktok", "twitter", "pinterest", "soundcloud")),
    "exception": ("Exception", ()),  # پیش‌فرض/باقی‌مونده
}


def _categorize(kind: str) -> str:
    k = (kind or "").lower()
    for cat_key, (_label, keywords) in BUG_CATEGORIES.items():
        if cat_key == "exception":
            continue
        if any(kw in k for kw in keywords):
            return cat_key
    return "exception"


def _clean(value, limit=1200):
    text = str(value or "").replace("`", "'")
    # قبلاً فقط GROQ_API_KEY و BOT_TOKEN سانسور می‌شدن؛ GROQ_API_KEY هیچ‌جای
    # پروژه استفاده نمی‌شه (باقی‌مونده‌ی یه تغییر قبلیه) و کلید واقعی که همه‌جا
    # به کار می‌ره (OPENROUTER_API_KEY) اصلاً تو این لیست نبود — یعنی اگه یه
    # خطای شبکه/HTTP متن کلید واقعی رو تو خودش داشت (مثلاً تو URL یا هدر)،
    # بدون سانسور مستقیم به پیام خطای اونر می‌رفت. الان همه‌ی کلیدهای حساس
    # پروژه سانسور می‌شن.
    for secret_name in (
        "OPENROUTER_API_KEY", "BOT_TOKEN", "TMDB_API_KEY", "AUDD_API_TOKEN", "GROQ_API_KEY",
    ):
        secret = os.getenv(secret_name)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text[:limit]


def remember_error(kind, exc, *, chat_id=None, user_id=None, extra=None):
    item = {
        "time": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "kind": _clean(kind, 80),
        "category": _categorize(kind),
        "error": _clean(f"{type(exc).__name__}: {exc}", 1000),
        "chat_id": chat_id,
        "user_id": user_id,
        "extra": _clean(extra, 500) if extra else "",
        "traceback": _clean(traceback.format_exc(), 3000),
    }
    RECENT_ERRORS.appendleft(item)
    return item


def format_error(item):
    lines = [
        "🚨 *خطای جدید ربات گاتهام*",
        "",
        f"🧩 بخش: {item['kind']}",
        f"❌ خطا: `{item['error']}`",
        f"🕐 زمان: {item['time']}",
    ]
    if item.get("chat_id") is not None:
        lines.append(f"💬 Chat ID: `{item['chat_id']}`")
    if item.get("user_id") is not None:
        lines.append(f"👤 User ID: `{item['user_id']}`")
    if item.get("extra"):
        lines += ["", f"📌 جزئیات: {item['extra']}"]
    lines += ["", "📄 Traceback:", f"```text\n{item['traceback']}\n```"]
    return "\n".join(lines)


async def report_error(bot: Bot, kind, exc, *, chat_id=None, user_id=None, extra=None):
    item = remember_error(kind, exc, chat_id=chat_id, user_id=user_id, extra=extra)
    owner_id = os.getenv("OWNER_ID") or os.getenv("ADMIN_ID")
    if not owner_id:
        # bot.py currently has a hard-coded OWNER_ID; caller can pass it through extra
        return item
    try:
        await bot.send_message(chat_id=int(owner_id), text=format_error(item), parse_mode="Markdown")
    except Exception:
        pass
    return item


def recent_errors_text(limit=8):
    if not RECENT_ERRORS:
        return "🛠 *رفع باگ ربات*\n\n✅ فعلاً خطای ثبت‌شده‌ای در این اجرای ربات نداریم."
    lines = ["🛠 *رفع باگ ربات*", "", "🚨 آخرین خطاهای ثبت‌شده:", ""]
    for i, item in enumerate(list(RECENT_ERRORS)[:limit], 1):
        lines.append(f"{i}. `{item['time']}` — *{item['kind']}* — `{item['error'][:180]}`")
    lines += ["", "⚡️ خطاهای جدید به‌صورت خودکار برای مالک ربات ارسال می‌شوند."]
    return "\n".join(lines)


def category_counts():
    """چند تا خطا (تو حافظه‌ی همین اجرای ربات) تو هر دسته ثبت شده."""
    counts = {cat_key: 0 for cat_key in BUG_CATEGORIES}
    for item in RECENT_ERRORS:
        cat = item.get("category") or _categorize(item.get("kind", ""))
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def errors_by_category_text(cat_key: str, limit=15):
    label = BUG_CATEGORIES.get(cat_key, (cat_key, ()))[0]
    items = [it for it in RECENT_ERRORS if (it.get("category") or _categorize(it.get("kind", ""))) == cat_key]
    if not items:
        return f"📜 *لاگ خطاها — {label}*\n\n✅ خطایی تو این دسته ثبت نشده."
    lines = [f"📜 *لاگ خطاها — {label}*", ""]
    for i, item in enumerate(items[:limit], 1):
        lines.append(f"{i}. `{item['time']}` — *{item['kind']}* — `{item['error'][:180]}`")
    return "\n".join(lines)


def clear_log():
    n = len(RECENT_ERRORS)
    RECENT_ERRORS.clear()
    return n


async def health_check_text(context) -> str:
    """🩺 GOTHAM HEALTH — بررسی سلامت اجزای اصلی ربات. هم زیر «رفع باگ ربات
    ← وضعیت ربات» و هم به‌عنوان Health Check مستقل (Phase 5) از همین یه تابع
    استفاده می‌شه — سیستم موازی ساخته نشده."""
    checks = []

    # Database — یه کوئری واقعی و سبک روی همون دیتابیس فعلی
    try:
        import bot as _bot
        conn = _bot._connect()
        conn.cursor().execute("SELECT 1")
        conn.close()
        checks.append(("Database", "🟢 OK", ""))
    except Exception as e:
        checks.append(("Database", "🔴 ERROR", _clean(e, 120)))

    # Handlers — تعداد Handlerهای واقعاً ثبت‌شده رو Application
    try:
        app = getattr(context, "application", None)
        total = sum(len(v) for v in app.handlers.values()) if app and getattr(app, "handlers", None) else 0
        checks.append(("Handlers", f"🟢 OK ({total} handler)" if total else "🟡 WARNING", ""))
    except Exception as e:
        checks.append(("Handlers", "🔴 ERROR", _clean(e, 120)))

    # Game Sessions — جمع بازی‌های فعال تو حافظه، از تمام ماژول‌های بازی
    try:
        active = 0
        for mod_name, attr_names in (
            ("card_room", ("WAR_GAMES", "BJ21_GAMES", "BLACKJACK_GAMES", "HOKM_GAMES",
                           "HAFT_GAMES", "CHARBARG_GAMES", "RUMMY_GAMES", "POKER_GAMES")),
            ("games_pack5", ("UNO_GAMES", "TER_GAMES", "BIL_GAMES", "RACE_GAMES")),
            ("group_rps", ("GRPS_GAMES",)),
            ("ttt_gotham", ("GTTT_GAMES",)),
        ):
            try:
                mod = __import__(mod_name)
                for attr in attr_names:
                    active += len(getattr(mod, attr, {}) or {})
            except Exception:
                continue
        checks.append(("Game Sessions", f"🟢 OK ({active} فعال)", ""))
    except Exception as e:
        checks.append(("Game Sessions", "🔴 ERROR", _clean(e, 120)))

    # Downloader
    try:
        import downloader  # noqa: F401
        checks.append(("Downloader", "🟢 OK", ""))
    except Exception as e:
        checks.append(("Downloader", "🔴 ERROR", _clean(e, 120)))

    # AI — قبلاً این چک روی GROQ_API_KEY بود، در حالی که موتور واقعی AI تو کل
    # پروژه (bot.py: call_ai، و media_recognition.py: تشخیص فیلم/آهنگ/خلاصه)
    # همه‌جا از OPENROUTER_API_KEY استفاده می‌کنن و GROQ_API_KEY هیچ‌جای دیگه‌ای
    # به کار نمی‌ره. نتیجه‌ی این باگ: حتی وقتی AI کاملاً سالم و فعال بود (چون
    # OPENROUTER_API_KEY ست شده)، این صفحه دروغ می‌گفت و WARNING نشون می‌داد.
    checks.append((
        "AI", "🟢 OK" if os.getenv("OPENROUTER_API_KEY") else "🟡 WARNING (بدون کلید OPENROUTER_API_KEY)", ""
    ))

    # Bug Reporter — همیشه OK چون داریم توش اجرا می‌شیم
    checks.append(("Bug Reporter", f"🟢 OK ({len(RECENT_ERRORS)} خطای اخیر تو حافظه)", ""))

    # Security
    try:
        import security_tools  # noqa: F401
        checks.append(("Security", "🟢 OK", ""))
    except Exception as e:
        checks.append(("Security", "🔴 ERROR", _clean(e, 120)))

    # Scheduler
    try:
        app = getattr(context, "application", None)
        has_jq = bool(app and getattr(app, "job_queue", None) is not None)
        checks.append(("Scheduler", "🟢 OK" if has_jq else "🟡 WARNING", ""))
    except Exception as e:
        checks.append(("Scheduler", "🔴 ERROR", _clean(e, 120)))

    lines = ["🩺 *GOTHAM HEALTH*", ""]
    for name, status, note in checks:
        lines.append(f"{status} — {name}" + (f" ({note})" if note else ""))
    return "\n".join(lines)
