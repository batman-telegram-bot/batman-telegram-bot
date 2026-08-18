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


def _clean(value, limit=1200):
    text = str(value or "").replace("`", "'")
    for secret_name in ("GROQ_API_KEY", "BOT_TOKEN"):
        secret = os.getenv(secret_name)
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text[:limit]


def remember_error(kind, exc, *, chat_id=None, user_id=None, extra=None):
    item = {
        "time": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        "kind": _clean(kind, 80),
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
