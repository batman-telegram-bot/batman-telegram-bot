# -*- coding: utf-8 -*-
"""
Midnight Gotham Announcement
-----------------------------
هر شب دقیقاً ساعت ۰۰:۰۰ به وقت تهران،
برای همه‌ی گروه‌هایی که ربات توشونه پیام گاتهامی می‌فرسته.
"""

import time as time_module
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

from gotham_content import pick_event_name, pick_dialogue_line

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


def _to_fa_digits(value):
    """تبدیل اعداد انگلیسی به اعداد فارسی."""
    return str(value).translate(
        str.maketrans(
            "0123456789",
            "۰۱۲۳۴۵۶۷۸۹"
        )
    )


def _format_percent(value):
    """درصد با دو رقم اعشار."""
    return _to_fa_digits(
        f"{value * 100:.2f}"
    ) + "%"


def _format_persian_date(now: datetime) -> str:
    if not HAS_JDATETIME:
        return "(برای تاریخ شمسی: pip install jdatetime)"

    jnow = jdatetime.datetime.fromgregorian(
        datetime=now
    )

    # روز هفته مستقیماً از تاریخ میلادی گرفته می‌شود
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


def _format_english_date(now: datetime) -> str:
    weekday = now.strftime("%A")

    month = MONTHS_EN[now.month - 1]

    date_text = (
        f"{now.year:04d}/"
        f"{now.month:02d}/"
        f"{now.day:02d}"
    )

    return f"{weekday} - {date_text} ({month})"


def _format_hijri_date(now: datetime) -> str:
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


def _bar(fraction: float, length: int = 5) -> str:
    fraction = max(
        0.0,
        min(1.0, fraction)
    )

    filled = round(
        fraction * length
    )

    return (
        "▰" * filled +
        "▱" * (length - filled)
    )


def _jalali_year_progress(now: datetime):
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

    total = (
        next_start - start
    ).days

    passed = (
        jnow.date() - start
    ).days + 1

    remaining = total - passed

    pct = passed / total

    return passed, remaining, pct


def _gregorian_year_progress(now: datetime):
    passed = now.timetuple().tm_yday

    year = now.year

    is_leap = (
        year % 4 == 0 and
        year % 100 != 0
    ) or (
        year % 400 == 0
    )

    total = 366 if is_leap else 365

    remaining = total - passed

    pct = passed / total

    return passed, remaining, pct


def build_full_datetime_text() -> str:
    """گزارش کامل تاریخ و ساعت به سبک گاتهام."""

    from gotham_content import gotham_signature_line

    now = datetime.now(TEHRAN_TZ)

    fa_str = _format_persian_date(now)

    en_str = _format_english_date(now)

    hijri_str = _format_hijri_date(now)

    lines = [
        "🦇 *تاریخ و ساعت گاتهام* 🦇",
        "",
        "〰️〰️〰️〰️〰️〰️〰️",
        "",
        f"⏰ ساعت : "
        f"{_to_fa_digits(now.strftime('%H:%M:%S'))}",

        f"📅 تاریخ : {fa_str}",
    ]

    if hijri_str:
        lines.append(
            f"🌙 تاریخ قمری : {hijri_str}"
        )
    else:
        lines.append(
            "🌙 تاریخ قمری : "
            "(برای فعال شدن: pip install hijri-converter)"
        )

    lines.append(
        f"☀️ تاریخ میلادی : {en_str}"
    )

    lines += [
        "",
        "🎉 تا پایان سال شمسی",
    ]

    jp = _jalali_year_progress(now)

    if jp:
        passed, remaining, pct = jp

        lines += [
            f"┘─ 📅 روزهای سپری‌شده : "
            f"{_to_fa_digits(passed)} روز",

            f"┘─ ⌛️ روزهای باقی‌مانده : "
            f"{_to_fa_digits(remaining)} روز",

            f"┘─ 🦇 {_format_percent(pct)} "
            f"{_bar(pct)}",
        ]

    gp = _gregorian_year_progress(now)

    passed, remaining, pct = gp

    lines += [
        "",
        "🎄 تا پایان سال میلادی",

        f"┘─ 📅 روزهای سپری‌شده : "
        f"{_to_fa_digits(passed)} روز",

        f"┘─ ⌛️ روزهای باقی‌مانده : "
        f"{_to_fa_digits(remaining)} روز",

        f"┘─ 🦇 {_format_percent(pct)} "
        f"{_bar(pct)}",

        "",
        "〰️〰️〰️〰️〰️〰️〰️",
        "",
        f"«{gotham_signature_line()}»",
    ]

    return "\n".join(lines)


def _get_all_chat_ids():
    """گرفتن chat_id تمام گروه‌ها از دیتابیس ربات."""

    import bot as _bot

    conn = _bot._connect()

    c = conn.cursor()

    c.execute(
        "SELECT chat_id FROM chats"
    )

    ids = [
        row["chat_id"]
        for row in c.fetchall()
    ]

    conn.close()

    return ids


def _special_event_for_date(now: datetime):
    """مناسبت‌های ویژه."""

    if now.month == 10 and now.day == 31:
        return (
            "🎃 Arkham's Halloween — هالووین آرکهام",
            "امشب حتی مجرم‌ها هم نقاب می‌زنن؛ من فرقی نمی‌کنم."
        )

    if now.month == 12 and now.day == 21:
        return (
            "🕯️ The Longest Night — طولانی‌ترین شب سال",
            "امشب طولانی‌ترین شبیه؛ برای من هر شب طولانیه."
        )

    if now.weekday() == 4 and now.day == 13:
        return (
            "🩸 Friday the 13th in Gotham — جمعه‌ی سیزدهم گاتهام",
            "امشب حتی شانس هم از گاتهام فرار کرده."
        )

    return None


async def midnight_announcement(context):
    """
    هر شب دقیقاً ساعت ۰۰:۰۰ به وقت تهران،
    پیام نجات گاتهام را برای همه گروه‌ها می‌فرستد.
    """

    now = datetime.now(TEHRAN_TZ)

    special = _special_event_for_date(now)

    if special:
        event, line = special
    else:
        event = pick_event_name()
        line = pick_dialogue_line()

    date_text = build_full_datetime_text()

    text = (
        "🌑 *نجات گاتهام آغاز شد* 🦇\n\n"
        "〰️〰️〰️〰️〰️〰️〰️\n\n"
        f"{date_text}\n\n"
        f"🦇 *رویداد امشب گاتهام*\n"
        f"{event}\n"
        f"«{line}»\n\n"
        "〰️〰️〰️〰️〰️〰️〰️\n"
        "🌃 گاتهام هنوز زنده است..."
    )

    try:
        chat_ids = _get_all_chat_ids()
    except Exception:
        chat_ids = []

    for chat_id in chat_ids:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
            )
        except Exception:
            pass

    try:
        import bot as _bot

        _bot._log_gotham_event(
            event,
            line
        )

    except Exception:
        pass

    # اول هر ماه میلادی
    if now.day == 1:
        await _announce_knight_of_month(
            context,
            chat_ids
        )


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
                    "🏆 *شوالیه‌ی این ماه گاتهام*\n\n"
                    f"{name} با بیشترین امتیاز، "
                    "لقب شوالیه‌ی ماه رو گرفت!\n"
                    "🦇 گاتهام بهت افتخار می‌کنه."
                ),
                parse_mode="Markdown",
            )

        except Exception:
            pass


async def morning_quote(context):
    """هر روز ساعت ۸ صبح یک دیالوگ گاتهامی می‌فرستد."""

    from gotham_content import gotham_signature_line

    try:
        chat_ids = _get_all_chat_ids()
    except Exception:
        chat_ids = []

    text = (
        "☀️ صبح گاتهام\n"
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


async def check_quiet_groups(context):
    """هر ۲ ساعت گروه‌های ساکت را بررسی می‌کند."""

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
                        "🌑 گاتهام مدتیه ساکته... "
                        "کسی نیست؟\n"
                        f"«{gotham_signature_line()}»"
                    ),
                )

                _bot._list_add(
                    chat_id,
                    "meta",
                    "quiet_notified",
                    last
                )

        except Exception:
            pass


def register_midnight_job(application):
    """
    ثبت Jobهای گاتهام.
    """

    if application.job_queue is None:

        import logging

        logging.getLogger(__name__).warning(
            "job_queue در دسترس نیست — برای فعال شدن "
            "پیام نیمه‌شب باید نصب شود:\n"
            'pip install "python-telegram-bot[job-queue]"'
        )

        return

    # 🌑 هر شب ساعت ۰۰:۰۰ به وقت تهران
    application.job_queue.run_daily(
        midnight_announcement,
        time=dtime(
            hour=0,
            minute=0,
            second=0,
            tzinfo=TEHRAN_TZ
        ),
        name="midnight_gotham_announcement",
    )

    # ☀️ هر روز ساعت ۸ صبح
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

    # 🌑 بررسی گروه‌های ساکت هر ۲ ساعت
    application.job_queue.run_repeating(
        check_quiet_groups,
        interval=2 * 3600,
        first=2 * 3600,
        name="gotham_quiet_group_check",
    )
