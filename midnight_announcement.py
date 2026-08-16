# -*- coding: utf-8 -*-

import time as time_module
import random
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

from gotham_content import pick_event_name, pick_dialogue_line


# =========================================================
# DATE
# =========================================================

try:
    import jdatetime
    HAS_JDATETIME = True
except ImportError:
    HAS_JDATETIME = False

try:
    from hijri_converter import Gregorian as _Gregorian
    HAS_HIJRI = True
except ImportError:
    HAS_HIJRI = False


TEHRAN_TZ = ZoneInfo("Asia/Tehran")


WEEKDAYS_FA = [
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنج‌شنبه",
    "جمعه",
    "شنبه",
    "یک‌شنبه",
]

MONTHS_FA = [
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
]

MONTHS_EN = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

HIJRI_MONTHS_FA = [
    "محرم",
    "صفر",
    "ربیع‌الاول",
    "ربیع‌الثانی",
    "جمادی‌الاول",
    "جمادی‌الثانی",
    "رجب",
    "شعبان",
    "رمضان",
    "شوال",
    "ذی‌القعده",
    "ذی‌الحجه",
]


# =========================================================
# GOTHAM DATABASE
# =========================================================

VILLAINS = [
    ("Joker", 96),
    ("Riddler", 84),
    ("Penguin", 78),
    ("Two-Face", 89),
    ("Bane", 93),
    ("Scarecrow", 87),
    ("Poison Ivy", 81),
    ("Mr. Freeze", 85),
    ("Harley Quinn", 76),
    ("Ra's al Ghul", 98),
    ("Black Mask", 88),
    ("Deathstroke", 94),
]


LOCATIONS = [
    "Crime Alley",
    "Arkham Asylum",
    "Wayne Tower",
    "Gotham Docks",
    "Gotham PD",
    "The Narrows",
    "Iceberg Lounge",
    "Old Gotham",
    "Robinson Park",
    "Burnley",
]


MISSIONS = [
    "ردپای یک مجرم ناشناس در Crime Alley پیدا شده؛ منطقه را بررسی کنید.",
    "یک سیگنال ناشناس از Arkham دریافت شده؛ واحدها آماده باشند.",
    "انتقال غیرقانونی در اسکله‌های گاتهام شناسایی شده است.",
    "دوربین‌های Wayne Tower برای چند ثانیه از کار افتاده‌اند.",
    "یک پرونده قدیمی دوباره فعال شده است؛ تمام شواهد بررسی شوند.",
    "فعالیت مشکوکی در The Narrows گزارش شده است.",
    "یک پیام رمزگذاری‌شده در شبکه پلیس گاتهام پیدا شده.",
    "یک مظنون ناشناس در Old Gotham مشاهده شده است.",
    "ردپای نقشه‌ای برای ایجاد آشوب در شهر پیدا شده است.",
    "تمام نگهبانان گاتهام تا طلوع در حالت آماده‌باش بمانند.",
]


FINAL_MESSAGES = [
    "چراغ‌ها خاموش شدند... اما گاتهام هنوز یک نگهبان دارد.",
    "گاتهام به خواب نمی‌رود. نگهبانان هم نباید بخوابند.",
    "جنایت می‌تواند در تاریکی پنهان شود، اما برای همیشه نه.",
    "تا وقتی چراغ گاتهام روشن است، امید زنده است.",
    "شب هنوز تمام نشده؛ مراقب سایه‌ها باشید.",
    "گاتهام هنوز زنده است. تا طلوع، شهر به نگهبان نیاز دارد.",
    "سایه‌ها عمیق‌تر شده‌اند؛ اما گاتهام هنوز سقوط نکرده است.",
]


EVIDENCE = [
    "اثر انگشت ناشناس",
    "کارت بازی جوکر",
    "پیام رمزگذاری‌شده",
    "ردپای کفش",
    "فیلم دوربین امنیتی",
    "قطعه‌ای از ماسک",
    "پوکه گلوله",
    "نمونه DNA",
    "نقشه دست‌نویس",
    "علامت ناشناس روی دیوار",
]


BATMAN_STATUS = [
    "در حال گشت در گاتهام",
    "در مسیر Crime Alley",
    "در Batcave",
    "در تعقیب یک مظنون",
    "در حال بررسی پرونده جدید",
    "در سایه‌های گاتهام ناپدید شده",
]


# =========================================================
# HELPERS
# =========================================================

def _to_fa_digits(value):
    return str(value).translate(
        str.maketrans(
            "0123456789",
            "۰۱۲۳۴۵۶۷۸۹"
        )
    )


def _bar(value, length=10):
    value = max(0, min(100, int(value)))
    filled = round(value / 100 * length)

    return "█" * filled + "░" * (length - filled)


def _stars(value):
    count = max(1, min(5, round(value / 20)))
    return "★" * count + "☆" * (5 - count)


def _format_percent(value):
    return _to_fa_digits(f"{value:.2f}") + "%"


# =========================================================
# DATE FORMAT
# =========================================================

def _format_persian_date(now):

    if not HAS_JDATETIME:
        return "(jdatetime نصب نشده)"

    jnow = jdatetime.datetime.fromgregorian(
        datetime=now
    )

    weekday = WEEKDAYS_FA[now.weekday()]
    month = MONTHS_FA[jnow.month - 1]

    date_text = (
        f"{jnow.year:04d}/"
        f"{jnow.month:02d}/"
        f"{jnow.day:02d}"
    )

    return (
        f"{weekday} - "
        f"{_to_fa_digits(date_text)} "
        f"({month})"
    )


def _format_hijri_date(now):

    if not HAS_HIJRI:
        return None

    h = _Gregorian(
        now.year,
        now.month,
        now.day
    ).to_hijri()

    weekday = WEEKDAYS_FA[now.weekday()]
    month = HIJRI_MONTHS_FA[h.month - 1]

    date_text = (
        f"{h.year:04d}/"
        f"{h.month:02d}/"
        f"{h.day:02d}"
    )

    return (
        f"{weekday} - "
        f"{_to_fa_digits(date_text)} "
        f"({month})"
    )


def _format_english_date(now):

    weekday = now.strftime("%A")
    month = MONTHS_EN[now.month - 1]

    return (
        f"{weekday} - "
        f"{now.year:04d}/"
        f"{now.month:02d}/"
        f"{now.day:02d} "
        f"({month})"
    )


# =========================================================
# YEAR PROGRESS
# =========================================================

def _jalali_year_progress(now):

    if not HAS_JDATETIME:
        return None

    jnow = jdatetime.datetime.fromgregorian(
        datetime=now
    )

    start = jdatetime.date(
        jnow.year,
        1,
        1
    )

    next_start = jdatetime.date(
        jnow.year + 1,
        1,
        1
    )

    total = (next_start - start).days

    passed = (jnow.date() - start).days + 1

    remaining = total - passed

    percent = passed / total * 100

    return passed, remaining, percent


def _gregorian_year_progress(now):

    passed = now.timetuple().tm_yday

    leap = (
        now.year % 4 == 0
        and (
            now.year % 100 != 0
            or now.year % 400 == 0
        )
    )

    total = 366 if leap else 365

    remaining = total - passed

    percent = passed / total * 100

    return passed, remaining, percent


# =========================================================
# DATE BLOCK
# =========================================================

def _build_date_block(now):

    fa_date = _format_persian_date(now)
    hijri_date = _format_hijri_date(now)
    en_date = _format_english_date(now)

    jp = _jalali_year_progress(now)
    gp = _gregorian_year_progress(now)

    lines = [
        "📅 DATE & TIME",
        "━━━━━━━━━━━━━━━━━━",
        f"⏰ ساعت: {_to_fa_digits(now.strftime('%H:%M:%S'))}",
        f"📅 شمسی: {fa_date}",
    ]

    if hijri_date:
        lines.append(
            f"🌙 قمری: {hijri_date}"
        )

    lines.append(
        f"☀️ میلادی: {en_date}"
    )

    if jp:
        passed, remaining, percent = jp

        lines += [
            "",
            "🎉 پیشرفت سال شمسی",
            f"└─ سپری‌شده: {_to_fa_digits(passed)} روز",
            f"└─ باقی‌مانده: {_to_fa_digits(remaining)} روز",
            f"└─ {_format_percent(percent)} "
            f"{_bar(percent)}",
        ]

    passed, remaining, percent = gp

    lines += [
        "",
        "🎄 پیشرفت سال میلادی",
        f"└─ سپری‌شده: {_to_fa_digits(passed)} روز",
        f"└─ باقی‌مانده: {_to_fa_digits(remaining)} روز",
        f"└─ {_format_percent(percent)} "
        f"{_bar(percent)}",
    ]

    return "\n".join(lines)


# =========================================================
# GOTHAM CITY STATUS
# =========================================================

def _build_city_status():

    locations = random.sample(
        LOCATIONS,
        5
    )

    statuses = [
        "🟢 امن",
        "🟢 تحت کنترل",
        "🟡 مشکوک",
        "🟠 خطرناک",
        "🔴 بحرانی",
    ]

    random.shuffle(statuses)

    lines = [
        "🏙️ GOTHAM CITY STATUS",
        "━━━━━━━━━━━━━━━━━━",
    ]

    for location, status in zip(
        locations,
        statuses
    ):
        lines.append(
            f"{status}  {location}"
        )

    return "\n".join(lines)


# =========================================================
# NIGHT CONDITIONS
# =========================================================

def _build_night_conditions():

    darkness = random.randint(70, 99)
    visibility = random.randint(15, 65)
    rain = random.randint(0, 100)
    police = random.randint(30, 95)

    return (
        "🌑 NIGHT CONDITIONS\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🌑 Darkness: {_to_fa_digits(darkness)}٪\n"
        f"👁 Visibility: {_to_fa_digits(visibility)}٪\n"
        f"🌧 Rain Probability: {_to_fa_digits(rain)}٪\n"
        f"🚔 Police Activity: {_to_fa_digits(police)}٪"
    )


# =========================================================
# BAT-SIGNAL
# =========================================================

def _build_bat_signal():

    active = random.choice([
        True,
        True,
        True,
        False,
    ])

    if active:

        response = random.randint(
            30,
            299
        )

        minutes = response // 60
        seconds = response % 60

        return (
            "🦇 BAT-SIGNAL\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📡 وضعیت: 🟢 ACTIVE\n"
            "📍 موقعیت: Gotham City\n"
            f"⏱ زمان پاسخ: "
            f"{_to_fa_digits(minutes):0>2}:"
            f"{_to_fa_digits(seconds):0>2}"
        )

    return (
        "🦇 BAT-SIGNAL\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📡 وضعیت: 🔴 NO RESPONSE\n"
        "📍 موقعیت: UNKNOWN\n"
        "⚠️ Batman is missing."
    )


# =========================================================
# NIGHTLY REPORT
# =========================================================

def _build_nightly_report(now):

    villain, villain_threat = random.choice(
        VILLAINS
    )

    location = random.choice(
        LOCATIONS
    )

    mission = random.choice(
        MISSIONS
    )

    evidence = random.sample(
        EVIDENCE,
        3
    )

    case_number = random.randint(
        1000,
        9999
    )

    active_criminals = random.randint(
        8,
        47
    )

    open_cases = random.randint(
        3,
        19
    )

    threat = random.randint(
        45,
        100
    )

    if threat >= 90:
        threat_status = "⚫ APOCALYPSE"
        alert = "⚠️ ALL UNITS — CODE BLACK"
    elif threat >= 75:
        threat_status = "🔴 CRITICAL"
        alert = "⚠️ ALL UNITS — CODE RED"
    elif threat >= 55:
        threat_status = "🟠 DANGER"
        alert = "🚨 HIGH ALERT"
    else:
        threat_status = "🟡 WARNING"
        alert = "⚠️ STAY ALERT"

    batman_status = random.choice(
        BATMAN_STATUS
    )

    ai_joker_probability = random.randint(
        20,
        95
    )

    organized_probability = random.randint(
        35,
        95
    )

    conflict_probability = random.randint(
        40,
        99
    )

    final_message = random.choice(
        FINAL_MESSAGES
    )

    date_block = _build_date_block(now)

    report = (
        "🌑 GOTHAM NIGHTLY REPORT 🦇\n"
        "━━━━━━━━━━━━━━━━━━\n\n"

        f"{date_block}\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "🚨 GOTHAM THREAT LEVEL\n"
        f"{threat_status}\n"
        f"{_bar(threat)} "
        f"{_to_fa_digits(threat)}٪\n"
        f"{alert}\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "📡 GOTHAM INTELLIGENCE\n"
        f"👤 مجرم‌های فعال: "
        f"{_to_fa_digits(active_criminals)}\n"
        f"📁 پرونده‌های باز: "
        f"{_to_fa_digits(open_cases)}\n"
        f"🦇 وضعیت بتمن: {batman_status}\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "🎭 VILLAIN OF THE NIGHT\n"
        f"☠️ TARGET: {villain}\n"
        f"⚠️ Threat: {_to_fa_digits(villain_threat)}٪\n"
        f"💀 Danger: {_stars(villain_threat)}\n"
        "🔴 Status: AT LARGE\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "📁 CASE FILE\n"
        f"🔢 پرونده: #{_to_fa_digits(case_number)}\n"
        f"📍 منطقه: {location}\n"
        "🔴 وضعیت: OPEN\n\n"

        "🔎 شواهد کشف‌شده:\n"
        f"• {evidence[0]}\n"
        f"• {evidence[1]}\n"
        f"• {evidence[2]}\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "🎯 NIGHT MISSION\n"
        f"{mission}\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        f"{_build_city_status()}\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        f"{_build_night_conditions()}\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        f"{_build_bat_signal()}\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "🧠 GOTHAM AI ANALYSIS\n"
        f"📊 عملیات سازمان‌یافته: "
        f"{_to_fa_digits(organized_probability)}٪\n"
        f"📊 احتمال دخالت Joker: "
        f"{_to_fa_digits(ai_joker_probability)}٪\n"
        f"📊 احتمال درگیری: "
        f"{_to_fa_digits(conflict_probability)}٪\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "📡 FINAL TRANSMISSION\n"
        f"«{final_message}»\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "🌃 GOTHAM NEVER SLEEPS.\n"
        "🦇 END OF REPORT"
    )

    return report, villain, mission


# =========================================================
# DATABASE
# =========================================================

def _get_all_chat_ids():

    import bot as _bot

    conn = _bot._connect()

    cursor = conn.cursor()

    cursor.execute(
        "SELECT chat_id FROM chats"
    )

    ids = [
        row["chat_id"]
        for row in cursor.fetchall()
    ]

    conn.close()

    return ids


# =========================================================
# SPECIAL EVENTS
# =========================================================

def _special_event_for_date(now):

    if now.month == 10 and now.day == 31:
        return (
            "🎃 Arkham Halloween",
            "امشب حتی مجرم‌ها هم نقاب می‌زنن."
        )

    if now.month == 12 and now.day == 21:
        return (
            "🕯️ The Longest Night",
            "طولانی‌ترین شب سال از راه رسیده."
        )

    if now.weekday() == 4 and now.day == 13:
        return (
            "🩸 Friday the 13th",
            "امشب حتی شانس هم از گاتهام فرار کرده."
        )

    return None


# =========================================================
# MIDNIGHT
# =========================================================

async def midnight_announcement(context):

    """
    هر شب ساعت ۰۰:۰۰ به وقت تهران
    گزارش کامل GOTHAM NIGHTLY REPORT ارسال می‌شود.
    """

    now = datetime.now(
        TEHRAN_TZ
    )

    report, villain, mission = _build_nightly_report(
        now
    )

    try:
        chat_ids = _get_all_chat_ids()
    except Exception:
        chat_ids = []

    for chat_id in chat_ids:

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=report,
            )

        except Exception:
            pass

    try:
        import bot as _bot

        _bot._log_gotham_event(
            villain,
            mission
        )

    except Exception:
        pass

    if now.day == 1:
        await _announce_knight_of_month(
            context,
            chat_ids
        )


# =========================================================
# KNIGHT OF MONTH
# =========================================================

async def _announce_knight_of_month(
    context,
    chat_ids
):

    import bot as _bot

    for chat_id in chat_ids:

        try:

            rows = _bot._get_leaderboard(
                chat_id,
                limit=1
            )

            if not rows:
                continue

            top = rows[0]

            name = (
                f"@{top['username']}"
                if top["username"]
                else "شهروند ناشناس"
            )

            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "🏆 شوالیه‌ی این ماه گاتهام 🦇\n\n"
                    f"{name} با بیشترین امتیاز، "
                    "شوالیه‌ی ماه شد.\n\n"
                    "🌃 گاتهام بهت افتخار می‌کنه."
                )
            )

        except Exception:
            pass


# =========================================================
# MORNING
# =========================================================

async def morning_quote(context):

    from gotham_content import gotham_signature_line

    try:
        chat_ids = _get_all_chat_ids()
    except Exception:
        chat_ids = []

    text = (
        "☀️ GOTHAM MORNING TRANSMISSION\n\n"
        f"«{gotham_signature_line()}»"
    )

    for chat_id in chat_ids:

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text
            )
        except Exception:
            pass


# =========================================================
# QUIET GROUPS
# =========================================================

async def check_quiet_groups(context):

    import bot as _bot

    from gotham_content import gotham_signature_line

    now = time_module.time()

    try:
        chat_ids = _get_all_chat_ids()
    except Exception:
        chat_ids = []

    for chat_id in chat_ids:

        try:

            last = _bot._list_get_one(
                chat_id,
                "meta",
                "last_msg_ts"
            )

            already_notified = _bot._list_get_one(
                chat_id,
                "meta",
                "quiet_notified"
            )

            if not last:
                continue

            gap = now - float(last)

            if (
                gap > 12 * 3600
                and already_notified != last
            ):

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "🌑 GOTHAM SILENCE ALERT\n\n"
                        "📡 بیش از ۱۲ ساعت است که "
                        "هیچ فعالیتی ثبت نشده.\n\n"
                        "🏙️ گاتهام منتظر شماست.\n\n"
                        f"«{gotham_signature_line()}»"
                    )
                )

                _bot._list_add(
                    chat_id,
                    "meta",
                    "quiet_notified",
                    last
                )

        except Exception:
            pass


# =========================================================
# REGISTER JOBS
# =========================================================

def register_midnight_job(application):

    if application.job_queue is None:

        import logging

        logging.getLogger(__name__).warning(
            "job_queue در دسترس نیست. "
            'pip install "python-telegram-bot[job-queue]"'
        )

        return

    # 🌑 00:00 — GOTHAM NIGHTLY REPORT
    application.job_queue.run_daily(
        midnight_announcement,
        time=dtime(
            hour=0,
            minute=0,
            second=0,
            tzinfo=TEHRAN_TZ
        ),
        name="gotham_nightly_report",
    )

    # ☀️ 08:00 — Morning Transmission
    application.job_queue.run_daily(
        morning_quote,
        time=dtime(
            hour=8,
            minute=0,
            second=0,
            tzinfo=TEHRAN_TZ
        ),
        name="gotham_morning_quote",
    )

    # 🌑 Every 2 hours — Quiet Groups
    application.job_queue.run_repeating(
        check_quiet_groups,
        interval=2 * 3600,
        first=2 * 3600,
        name="gotham_quiet_group_check",
    )
