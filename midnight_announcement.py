# -*- coding: utf-8 -*-

import random
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import jdatetime
from hijri_converter import Gregorian

TEHRAN_TZ = ZoneInfo("Asia/Tehran")


# =========================================================
# GOTHAM DATA
# =========================================================

VILLAINS = [
    "Joker",
    "Riddler",
    "Penguin",
    "Two-Face",
    "Bane",
    "Scarecrow",
    "Poison Ivy",
    "Mr. Freeze",
    "Harley Quinn",
    "Black Mask",
]

LOCATIONS = [
    "Crime Alley",
    "Arkham Asylum",
    "The Narrows",
    "Gotham Docks",
    "Wayne Tower",
    "Gotham PD",
    "Old Gotham",
    "Robinson Park",
    "Iceberg Lounge",
]

MISSIONS = [
    "ردیابی یک سیگنال ناشناس",
    "بررسی فعالیت مشکوک در منطقه",
    "پیدا کردن ردپای یک مظنون ناشناس",
    "بررسی پیام رمزگذاری‌شده",
    "شناسایی منبع سیگنال ناشناس",
    "بررسی حرکت مشکوک در گاتهام",
    "ردگیری یک پرونده قدیمی",
]

BATMAN_STATUS = [
    "در حال گشت",
    "در حال بررسی پرونده",
    "در تعقیب مظنون",
    "در حال گشت در Crime Alley",
    "در Batcave",
    "در سایه‌های گاتهام",
]

FINAL_MESSAGES = [
    "گاتهام هنوز بیداره...",
    "شب هنوز تمام نشده...",
    "سایه‌ها هنوز در گاتهام حرکت می‌کنند...",
    "تا طلوع، شهر به نگهبان نیاز دارد...",
    "گاتهام به خواب نمی‌رود...",
    "امشب هم گاتهام یک نگهبان دارد...",
]


# =========================================================
# HELPERS
# =========================================================

def fa_num(value):
    return str(value).translate(
        str.maketrans(
            "0123456789",
            "۰۱۲۳۴۵۶۷۸۹"
        )
    )


def make_bar(percent, length=10):
    filled = round(percent / 100 * length)
    filled = max(0, min(length, filled))

    return "█" * filled + "░" * (length - filled)


# =========================================================
# DATE
# =========================================================

def get_date_info(now):
    j = jdatetime.datetime.fromgregorian(
        datetime=now
    )

    weekday_fa = [
        "دوشنبه",
        "سه‌شنبه",
        "چهارشنبه",
        "پنج‌شنبه",
        "جمعه",
        "شنبه",
        "یکشنبه",
    ][now.weekday()]

    jalali_months = [
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

    hijri_months = [
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

    h = Gregorian(
        now.year,
        now.month,
        now.day
    ).to_hijri()

    jalali_date = (
        f"{j.year:04d}/"
        f"{j.month:02d}/"
        f"{j.day:02d}"
    )

    hijri_date = (
        f"{h.year:04d}/"
        f"{h.month:02d}/"
        f"{h.day:02d}"
    )

    english_month = now.strftime("%B")
    english_weekday = now.strftime("%A")

    return {
        "weekday_fa": weekday_fa,
        "jalali": jalali_date,
        "jalali_month": jalali_months[j.month - 1],
        "hijri": hijri_date,
        "hijri_month": hijri_months[h.month - 1],
        "english_weekday": english_weekday,
        "english_month": english_month,
    }


# =========================================================
# FULL DATE / TIME
# =========================================================

def build_full_datetime_text():
    now = datetime.now(TEHRAN_TZ)

    date = get_date_info(now)

    return (
        f"🦇 تایم گاتهام : "
        f"{fa_num(now.strftime('%H:%M:%S'))}\n"

        f"🌃 روز گاتهام : "
        f"{date['weekday_fa']} - "
        f"{fa_num(date['jalali'])} "
        f"({date['jalali_month']})\n"

        f"🌙 تقویم قمری : "
        f"{date['weekday_fa']} - "
        f"{fa_num(date['hijri'])} "
        f"({date['hijri_month']})\n"

        f"☀️ تقویم میلادی : "
        f"{date['english_weekday']} - "
        f"{now.strftime('%Y/%m/%d')} "
        f"({date['english_month']})"
    )


# =========================================================
# YEAR PROGRESS
# =========================================================

def jalali_progress(now):
    j = jdatetime.date.fromgregorian(
        date=now.date()
    )

    start = jdatetime.date(
        j.year,
        1,
        1
    )

    next_year = jdatetime.date(
        j.year + 1,
        1,
        1
    )

    total = (next_year - start).days
    passed = (j - start).days + 1
    remaining = total - passed

    percent = passed / total * 100

    return passed, remaining, percent


def gregorian_progress(now):
    day_of_year = now.timetuple().tm_yday

    leap = (
        now.year % 4 == 0
        and (
            now.year % 100 != 0
            or now.year % 400 == 0
        )
    )

    total = 366 if leap else 365

    remaining = total - day_of_year
    percent = day_of_year / total * 100

    return day_of_year, remaining, percent


# =========================================================
# MIDNIGHT MESSAGE
# =========================================================

def build_midnight_message():
    now = datetime.now(TEHRAN_TZ)

    date = get_date_info(now)

    jalali_passed, jalali_remaining, jalali_percent = (
        jalali_progress(now)
    )

    greg_passed, greg_remaining, greg_percent = (
        gregorian_progress(now)
    )

    # Random Gotham information
    threat = random.randint(55, 100)

    if threat >= 90:
        threat_status = "🔴 بحرانی"
    elif threat >= 75:
        threat_status = "🟠 خطرناک"
    elif threat >= 60:
        threat_status = "🟡 هشدار"
    else:
        threat_status = "🟢 عادی"

    villain = random.choice(VILLAINS)
    location = random.choice(LOCATIONS)
    mission = random.choice(MISSIONS)
    batman = random.choice(BATMAN_STATUS)
    final_message = random.choice(FINAL_MESSAGES)

    # Bat-Signal
    bat_signal = random.choice([
        "🟢 فعال",
        "🟢 فعال",
        "🟢 فعال",
        "🟡 ضعیف",
        "🔴 خاموش",
    ])

    message = (
        "🌑 GOTHAM NIGHTLY REPORT 🦇\n\n"

        "〰️〰️〰️〰️〰️〰️〰️\n\n"

        f"⏰ ساعت : "
        f"{fa_num(now.strftime('%H:%M:%S'))}\n"

        f"📅 تاریخ : "
        f"{date['weekday_fa']} - "
        f"{fa_num(date['jalali'])} "
        f"({date['jalali_month']})\n"

        f"🌙 تاریخ قمری : "
        f"{date['weekday_fa']} - "
        f"{fa_num(date['hijri'])} "
        f"({date['hijri_month']})\n"

        f"☀️ تاریخ میلادی : "
        f"{date['english_weekday']} - "
        f"{now.strftime('%Y/%m/%d')} "
        f"({date['english_month']})\n\n"

        "🎉 تا پایان سال شمسی\n"

        f"┘─ 📅 روزهای سپری‌شده : "
        f"{fa_num(jalali_passed)} روز\n"

        f"┘─ ⌛️ روزهای باقی‌مانده : "
        f"{fa_num(jalali_remaining)} روز\n"

        f"┘─ 🦇 {fa_num(f'{jalali_percent:.2f}')}% "
        f"{make_bar(jalali_percent, 5)}\n\n"

        "🎄 تا پایان سال میلادی\n"

        f"┘─ 📅 روزهای سپری‌شده : "
        f"{fa_num(greg_passed)} روز\n"

        f"┘─ ⌛️ روزهای باقی‌مانده : "
        f"{fa_num(greg_remaining)} روز\n"

        f"┘─ 🦇 {fa_num(f'{greg_percent:.2f}')}% "
        f"{make_bar(greg_percent, 5)}\n\n"

        "〰️〰️〰️〰️〰️〰️〰️\n\n"

        f"🚨 وضعیت گاتهام : {threat_status}\n"

        f"🦇 {fa_num(threat)}% "
        f"{make_bar(threat)}\n\n"

        f"🎭 شرور امشب : {villain}\n"

        f"📍 منطقه : {location}\n"

        f"🦇 وضعیت بتمن : {batman}\n\n"

        "🎯 مأموریت امشب\n"

        f"└─ {mission}\n\n"

        f"📡 Bat-Signal : {bat_signal}\n\n"

        "〰️〰️〰️〰️〰️〰️〰️\n\n"

        f"«{final_message}»\n\n"

        "🌃 GOTHAM NEVER SLEEPS."
    )

    return message


# =========================================================
# SEND TO ALL CHATS
# =========================================================

async def midnight_announcement(context):
    try:
        import bot as _bot

        conn = _bot._connect()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT chat_id FROM chats"
        )

        chat_ids = [
            row["chat_id"]
            for row in cursor.fetchall()
        ]

        conn.close()

    except Exception:
        return

    message = build_midnight_message()

    for chat_id in chat_ids:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message
            )
        except Exception:
            pass


# =========================================================
# REGISTER
# =========================================================

def register_midnight_job(application):

    if application.job_queue is None:
        print(
            "ERROR: JobQueue فعال نیست. "
            'نصب کنید: python-telegram-bot[job-queue]==21.6'
        )
        return

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
