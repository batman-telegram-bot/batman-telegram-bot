# -*- coding: utf-8 -*-
"""
Midnight Gotham Announcement
-----------------------------
هر شب دقیقاً ساعت ۰۰:۰۰ به وقت تهران، برای همه‌ی گروه‌هایی که ربات توشونه
(خودکار از دیتابیس ربات پیدا می‌شن، نیازی به وارد کردن دستی chat_id نیست)،
تاریخ (فارسی + انگلیسی) + یه اسم رویداد گاتهامی + یه دیالوگ بتمنی می‌فرسته.

نصب پکیج تاریخ شمسی (اختیاری ولی پیشنهادی):
    pip install jdatetime

نحوه‌ی وصل کردن به bot.py (داخل تابع main، بعد از ساخت app):

    from midnight_announcement import register_midnight_job
    register_midnight_job(app)
"""

from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

from gotham_content import pick_event_name, pick_dialogue_line

try:
    import jdatetime
    HAS_JDATETIME = True
except ImportError:
    HAS_JDATETIME = False

TEHRAN_TZ = ZoneInfo("Asia/Tehran")

WEEKDAYS_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یک‌شنبه"]
MONTHS_FA = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def _format_persian_date(now: datetime) -> str:
    if not HAS_JDATETIME:
        return "(برای تاریخ شمسی: pip install jdatetime)"
    jnow = jdatetime.datetime.fromgregorian(datetime=now)
    weekday = WEEKDAYS_FA[jnow.weekday()]
    month = MONTHS_FA[jnow.month - 1]
    return f"{weekday} {jnow.day} {month} {jnow.year} ساعت {now.strftime('%H:%M')}"


def _format_english_date(now: datetime) -> str:
    return now.strftime("%A, %B %d, %Y - %H:%M")


def _get_all_chat_ids():
    """چت‌آیدی همه‌ی گروه‌هایی که ربات توشون فعاله رو از دیتابیس خود ربات می‌گیره -
    نیازی به هاردکد کردن نیست. ایمپورت داخل تابعه تا سیکل ایمپورت با bot.py پیش نیاد."""
    import bot as _bot
    conn = _bot._connect()
    c = conn.cursor()
    c.execute("SELECT chat_id FROM chats")
    ids = [row["chat_id"] for row in c.fetchall()]
    conn.close()
    return ids


def _special_event_for_date(now: datetime):
    """اگه امروز یه مناسبت خاصه، یه رویداد/دیالوگ ویژه برمی‌گردونه؛ وگرنه None."""
    if now.month == 10 and now.day == 31:
        return ("🎃 Arkham's Halloween — هالووین آرکهام", "امشب حتی مجرم‌ها هم نقاب می‌زنن؛ من فرقی نمی‌کنم.")
    if now.month == 12 and now.day == 21:
        return ("🕯️ The Longest Night — طولانی‌ترین شب سال", "امشب طولانی‌ترین شبیه؛ برای من هر شب طولانیه.")
    if now.weekday() == 4 and now.day == 13:  # جمعه‌ی سیزدهم
        return ("🩸 Friday the 13th in Gotham — جمعه‌ی سیزدهم گاتهام", "امشب حتی شانس هم از گاتهام فرار کرده.")
    return None


async def midnight_announcement(context):
    now = datetime.now(TEHRAN_TZ)
    fa_str = _format_persian_date(now)
    en_str = _format_english_date(now)
    special = _special_event_for_date(now)
    if special:
        event, line = special
    else:
        event = pick_event_name()
        line = pick_dialogue_line()

    text = (
        "🌑 نیمه‌شب فرا رسید\n"
        f"📅 {fa_str}\n"
        f"📅 {en_str}\n\n"
        f"{event}\n"
        f"«{line}»"
    )

    try:
        chat_ids = _get_all_chat_ids()
    except Exception:
        chat_ids = []

    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
        except Exception:
            pass  # اگه ربات از یه گروه حذف شده باشه یا خطای دیگه‌ای بخوره، بی‌خیال اون یکی شو

    try:
        import bot as _bot
        _bot._log_gotham_event(event, line)
    except Exception:
        pass

    # 🏆 اول هر ماه (میلادی)، شوالیه‌ی ماه رو برای هر گروه اعلام کن
    if now.day == 1:
        await _announce_knight_of_month(context, chat_ids)


async def _announce_knight_of_month(context, chat_ids):
    import bot as _bot
    for chat_id in chat_ids:
        try:
            rows = _bot._get_leaderboard(chat_id, limit=1)
            if not rows:
                continue
            top = rows[0]
            name = f"@{top['username']}" if top["username"] else "شهروند ناشناس"
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "🏆 *شوالیه‌ی این ماه گاتهام*\n\n"
                    f"{name} با بیشترین امتیاز، لقب شوالیه‌ی ماه رو گرفت!\n"
                    "🦇 گاتهام بهت افتخار می‌کنه."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass


def register_midnight_job(application):
    """application: شیء Application ساخته‌شده تو bot.py. نیازی به chat_ids نیست،
    خودکار همه‌ی گروه‌های فعال رو از دیتابیس ربات پیدا می‌کنه."""
    if application.job_queue is None:
        # نسخه‌ی job-queue نصب نیست؛ برای فعال‌شدن این قابلیت باید نصبش کنی:
        #     pip install "python-telegram-bot[job-queue]"
        import logging
        logging.getLogger(__name__).warning(
            "job_queue در دسترس نیست — برای پیام نیمه‌شب باید pip install "
            "\"python-telegram-bot[job-queue]\" رو اجرا کنی."
        )
        return
    application.job_queue.run_daily(
        midnight_announcement,
        time=dtime(hour=0, minute=0, second=0, tzinfo=TEHRAN_TZ),
        name="midnight_gotham_announcement",
    )
