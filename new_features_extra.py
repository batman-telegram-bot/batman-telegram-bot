# -*- coding: utf-8 -*-
"""
new_features_extra.py
================
سه امکان جدید برای بخش «🧩 امکانات جدید»:

    🎡 چرخ گردون روزانه — یه‌بار در روز، «چرخ گردون» رو بگیر و امتیاز جایزه بگیر
       (روی همون سیستم امتیاز/players موجود سوار شده، اقتصاد جدید نساخته).
    🎫 تیکت پشتیبانی — تو چت خصوصی ربات بنویس «تیکت <متن>»، پیامت مستقیم برای
       سازنده‌ی ربات (OWNER_ID) فرستاده می‌شه.
    🎂 یادآور تولد — بنویس «تولدم ۱۵ مرداد» (یا هر فرمتی)، ربات هر روز چک می‌کنه
       و تو گروه‌هایی که عضوی، روز تولدت تبریک می‌گه.

این ماژول مثل بقیه، مستقیم به دیتابیس bot.py وصل نیست؛
register_new_features(app, deps) این‌ها رو می‌گیره:

    deps = {
        "get_player": ...,       # (chat_id, user_id, username) -> dict
        "save_player": ...,      # (player) -> None
        "get_inventory": ...,    # (player) -> dict
        "set_inventory": ...,    # (player, dict) -> None
        "db_run": ...,           # async(fn, *args) -> نتیجه fn تو ترد جدا
        "owner_id": ...,         # int
        "db_path": ...,          # str, مسیر همون bot.db برای جدول تولدها
    }
"""

import os
import time
import random
import sqlite3
import logging
from datetime import date, datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from telegram.ext import ContextTypes, MessageHandler, filters

log = logging.getLogger(__name__)

WHEEL_RE = filters.Regex(r"(?i)^\s*چرخ گردون\s*$")
TICKET_RE = filters.Regex(r"(?i)^\s*تیکت(\s+.+)?$")
BIRTHDAY_SET_RE = filters.Regex(r"(?i)^\s*تولدم\s+(.+)$")

WHEEL_PRIZES = [10, 15, 20, 25, 30, 50, 5, 100]  # آخری (۱۰۰) نادرتر می‌شه با وزن‌دهی پایین
WHEEL_WEIGHTS = [20, 18, 16, 14, 12, 8, 20, 2]

_FA_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def _init_birthday_table(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS birthdays (
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            month_day TEXT,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    conn.commit()
    conn.close()


def _set_birthday(db_path, chat_id, user_id, username, first_name, month_day):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO birthdays (chat_id, user_id, username, first_name, month_day) "
        "VALUES (?,?,?,?,?)",
        (chat_id, user_id, username, first_name, month_day),
    )
    conn.commit()
    conn.close()


def _get_today_birthdays(db_path, month_day):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT DISTINCT chat_id, user_id, username, first_name FROM birthdays WHERE month_day=?",
        (month_day,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _parse_persian_month_day(text: str):
    """یه ورودی مثل «۱۵ مرداد» یا «15 مرداد» رو به «۵-۱۵» (ماه-روز) تبدیل می‌کنه."""
    text = text.strip()
    digits_map = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    text = text.translate(digits_map)
    parts = text.split()
    day = None
    month = None
    for p in parts:
        if p.isdigit():
            day = int(p)
        else:
            for i, m in enumerate(_FA_MONTHS, 1):
                if p.strip("،.!") == m:
                    month = i
                    break
    if day and month and 1 <= day <= 31:
        return f"{month:02d}-{day:02d}"
    return None


def register_new_features(app, deps):
    get_player = deps["get_player"]
    save_player = deps["save_player"]
    get_inventory = deps["get_inventory"]
    set_inventory = deps["set_inventory"]
    db_run = deps["db_run"]
    owner_id = deps["owner_id"]
    db_path = deps["db_path"]

    _init_birthday_table(db_path)

    # --- چرخ گردون روزانه ---
    async def wheel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        user = update.effective_user
        player = await db_run(get_player, chat_id, user.id, user.username or "")
        inv = get_inventory(player)
        today = date.today().isoformat()
        if inv.get("last_wheel_date") == today:
            await update.effective_message.reply_text(
                "🎡 امروز چرخ گردون رو قبلاً چرخوندی — فردا دوباره بیا."
            )
            return
        prize = random.choices(WHEEL_PRIZES, weights=WHEEL_WEIGHTS, k=1)[0]
        player["score"] = (player.get("score") or 0) + prize
        inv["last_wheel_date"] = today
        set_inventory(player, inv)
        await db_run(save_player, player)
        await update.effective_message.reply_text(
            f"🎡 چرخ گردون چرخید... 🎉 بردی: +{prize} امتیاز گاتهام!\n(فردا دوباره می‌تونی بچرخونی)"
        )

    # --- تیکت پشتیبانی ---
    async def ticket_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type != ChatType.PRIVATE:
            await update.effective_message.reply_text(
                "🎫 برای تیکت پشتیبانی تو چت خصوصی ربات بنویس «تیکت <متنت>»."
            )
            return
        text = update.effective_message.text or ""
        body = text[len("تیکت"):].strip(" :،")
        if not body:
            await update.effective_message.reply_text("✏️ بعد از «تیکت» متن درخواستت رو بنویس.")
            return
        user = update.effective_user
        uname = f"@{user.username}" if user.username else "بدون یوزرنیم"
        try:
            await context.bot.send_message(
                owner_id,
                f"🎫 تیکت جدید از {user.first_name} ({uname} — آیدی {user.id}):\n\n{body}",
            )
        except Exception as e:
            log.warning(f"ticket forward failed: {e}")
            await update.effective_message.reply_text("⚠️ الان نشد تیکت رو بفرستم، دوباره امتحان کن.")
            return
        await update.effective_message.reply_text("🎫 تیکتت ثبت شد و برای پشتیبانی فرستاده شد. ممنون از صبرت 🦇")

    # --- تنظیم تولد ---
    async def birthday_set_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await update.effective_message.reply_text("🎂 این دستور رو تو گروه بنویس تا تو همون گروه تبریک بگیری.")
            return
        text = update.effective_message.text or ""
        raw = text[len("تولدم"):].strip()
        month_day = _parse_persian_month_day(raw)
        if not month_day:
            await update.effective_message.reply_text(
                "⚠️ فرمتش درست نبود. مثال: «تولدم ۱۵ مرداد»"
            )
            return
        user = update.effective_user
        chat_id = update.effective_chat.id
        await db_run(
            _set_birthday, db_path, chat_id, user.id, user.username or "", user.first_name or "", month_day
        )
        await update.effective_message.reply_text("🎂 ثبت شد! سر تاریخش تو همین گروه برات تبریک می‌گم.")

    async def birthday_daily_job(context: ContextTypes.DEFAULT_TYPE):
        today_key = datetime.now().strftime("%m-%d")
        rows = await db_run(_get_today_birthdays, db_path, today_key)
        for r in rows:
            name = f"@{r['username']}" if r["username"] else r["first_name"]
            try:
                await context.bot.send_message(
                    r["chat_id"],
                    f"🎂🦇 امروز تولد {name}‌ست! گاتهام امروز یه‌کم روشن‌تره، تولدت مبارک!",
                )
            except Exception:
                pass

    app.add_handler(MessageHandler(WHEEL_RE, wheel_cmd), group=25)
    app.add_handler(MessageHandler(TICKET_RE, ticket_cmd), group=25)
    app.add_handler(MessageHandler(BIRTHDAY_SET_RE, birthday_set_cmd), group=25)

    if getattr(app, "job_queue", None):
        from datetime import time as dtime
        try:
            from zoneinfo import ZoneInfo
            tehran = ZoneInfo("Asia/Tehran")
        except Exception:
            tehran = None
        app.job_queue.run_daily(birthday_daily_job, time=dtime(9, 0, tzinfo=tehran))
