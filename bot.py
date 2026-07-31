import os
import re
import json
import time
import random
import logging
import sqlite3
import asyncio
from datetime import datetime, date
from collections import defaultdict, deque

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)



# =========================================================
#  GAMES ENGINE (merged into a single file)
#  همه‌ی منطق بازی‌ها این‌جاست — برای اضافه کردن بازی جدید همین‌جا
#  یه GAME تازه به دیکشنری GAMES اضافه کن.
# =========================================================

# -*- coding: utf-8 -*-
"""
games.py
====================================================
موتور بازی‌های ربات — بدون نیاز به دستور «/» و بدون نیاز به منشن تو گروه.
هر بازی با نوشتن اسمش شروع می‌شه، و هر پاسخ بعدی کاربر به عنوان حدس/حرکت
همون بازی در نظر گرفته می‌شه تا وقتی بازی تموم بشه.

این ماژول «مرحله اول» از پروژه‌ست (۱۵ بازی). بقیه بازی‌ها (تا ۶۰ تا) در
مراحل بعدی به همین ساختار اضافه می‌شن — فقط کافیه یک ورودی جدید به
GAMES و در صورت نیاز یک session-handler کوچیک اضافه بشه.

لحن: طعنه‌دار و تند (بی‌عرضه/خرفت/دست‌وپاچلفتی/بازنده و مشابه) ولی بدون
فحش رکیک، ناسزای جنسی/خانوادگی، یا توهین نژادی/مذهبی. این خط قرمز ثابته.
"""

# =========================================================
#  حالت بازی‌ها (در حافظه — هر گروه فقط یک بازی فعال داره)
# =========================================================

GAME_SESSIONS = {}  # chat_id -> {"key": str, "user_id": int|None, "data": dict}


def get_session(chat_id):
    return GAME_SESSIONS.get(chat_id)


def clear_session(chat_id):
    GAME_SESSIONS.pop(chat_id, None)


def set_session(chat_id, key, data, user_id=None):
    GAME_SESSIONS[chat_id] = {"key": key, "user_id": user_id, "data": data}


# =========================================================
#  دیتای بازی‌ها
# =========================================================

TAUNTS_LOSE = [
    "آشغالی تو بازی، جدی می‌گم 🗑️",
    "خرفت شدی؟ همینو نمی‌تونی درست انجام بدی؟",
    "دست‌وپا چلفتی محض، حالم بهم خورد.",
    "بازنده‌ی همیشگی، تو رو بگو!",
    "بی‌مصرف بودی، از اول معلوم بود.",
    "این چه وضع بازی کردنه، خجالت بکش.",
    "گدای بردن، همینم بلد نیستی درست انجام بدی.",
    "حقته که همیشه ببازی، ضعیف.",
    "یه بار تو زندگیت درست کاری کن، حداقل تو بازی.",
]

TAUNTS_WIN = [
    "باریکلا، یه بار تو زندگیت درست حدس زدی 👏",
    "شانسی بردی، خودتم می‌دونی.",
    "آفرین، انتظار نداشتم ازت.",
    "قبول، این یکی رو بردی.",
]


def taunt_lose():
    return random.choice(TAUNTS_LOSE)


def taunt_win():
    return random.choice(TAUNTS_WIN)


CITIES = [
    {"name": "پاریس", "aliases": ["پاریس", "paris"], "clue": "پایتخت فرانسه، خونه‌ی برج ایفل 🗼"},
    {"name": "توکیو", "aliases": ["توکیو", "tokyo"], "clue": "پایتخت ژاپن، پر از نئون و شلوغی 🗾"},
    {"name": "قاهره", "aliases": ["قاهره", "cairo"], "clue": "پایتخت مصر، نزدیک اهرام ثلاثه 🏜️"},
    {"name": "استانبول", "aliases": ["استانبول", "istanbul"], "clue": "بین دو قاره، تنگه بسفر ازش رد می‌شه 🌉"},
    {"name": "نیویورک", "aliases": ["نیویورک", "new york"], "clue": "شهری که هیچ‌وقت نمی‌خوابه، مجسمه آزادی داره 🗽"},
    {"name": "دبی", "aliases": ["دبی", "dubai"], "clue": "برج خلیفه اونجاست، وسط کویره ولی پر از برج 🏙️"},
    {"name": "رم", "aliases": ["رم", "rome"], "clue": "کولوسئوم اونجاست، پایتخت ایتالیا 🏛️"},
    {"name": "لندن", "aliases": ["لندن", "london"], "clue": "بیگ‌بن و پادشاهی انگلیس، همیشه بارونی ☔"},
]

COUNTRIES = [
    {"name": "ژاپن", "aliases": ["ژاپن", "japan"], "clue": "کشور آفتاب تابان، صنعت انیمه و خودرو 🚗"},
    {"name": "برزیل", "aliases": ["برزیل", "brazil"], "clue": "بزرگ‌ترین کشور آمریکای جنوبی، عاشق فوتباله ⚽"},
    {"name": "مصر", "aliases": ["مصر", "egypt"], "clue": "کنار رود نیل، اهرام ثلاثه و فراعنه 🐫"},
    {"name": "کانادا", "aliases": ["کانادا", "canada"], "clue": "پر از برف و خرس، برگ افرا رو پرچمشه 🍁"},
    {"name": "استرالیا", "aliases": ["استرالیا", "australia"], "clue": "قاره‌ای که کانگورو توشه 🦘"},
    {"name": "آلمان", "aliases": ["آلمان", "germany"], "clue": "خودروسازی قوی و اکتبرفست معروفشه 🍺"},
]

COLORS = [
    {"name": "قرمز", "aliases": ["قرمز", "red"], "clue": "رنگ خون و عشق و خطر ❤️"},
    {"name": "آبی", "aliases": ["آبی", "blue"], "clue": "رنگ دریا و آسمون صاف 🔵"},
    {"name": "سبز", "aliases": ["سبز", "green"], "clue": "رنگ طبیعت و برگ درخت 🟢"},
    {"name": "زرد", "aliases": ["زرد", "yellow"], "clue": "رنگ خورشید و موز 🟡"},
    {"name": "بنفش", "aliases": ["بنفش", "purple"], "clue": "رنگ سلطنتی، ترکیب قرمز و آبی 🟣"},
]

HANGMAN_WORDS = ["گاتهام", "بتمن", "جوکر", "کامپیوتر", "تلگرام", "پایتون", "شبکه", "کتابخانه", "موشک"]

DARE_TRUTH = [
    ("truth", "آخرین دروغی که گفتی چی بود؟"),
    ("truth", "بدترین کاری که تا حالا کردی چیه؟"),
    ("truth", "از کی تو گروه بیشتر از همه خوشت میاد؟"),
    ("dare", "الان باید یه استیکر خنده‌دار تو گروه بفرستی!"),
    ("dare", "باید ۵ تا ایموجی که حس الانتو نشون میده بفرستی."),
    ("dare", "باید یه جمله رو برعکس بنویسی."),
]

WOULD_YOU_RATHER = [
    ("همیشه سردت باشه", "همیشه گرمت باشه"),
    ("پرواز کردن بلد باشی", "نامرئی بشی"),
    ("پولدار ولی تنها باشی", "فقیر ولی محبوب باشی"),
    ("هیچوقت نتونی دروغ بگی", "هیچوقت نتونی حقیقتو بگی"),
    ("عمرت رو تو گذشته بگذرونی", "عمرت رو تو آینده بگذرونی"),
]

PROVERBS = [
    ("کار نیکو کردن از پر کردن است", "کار نیکو کردن از ___ است", "پر کردن"),
    ("آب که از سر گذشت چه یک وجب چه صد وجب", "آب که از سر گذشت چه یک وجب چه ___ وجب", "صد"),
    ("تا تنور گرم است نان باید پخت", "تا تنور گرم است ___ باید پخت", "نان"),
    ("جوجه را آخر پاییز می‌شمارند", "جوجه را آخر ___ می‌شمارند", "پاییز"),
    ("دیوار موش داره موش هم گوش داره", "دیوار موش داره موش هم ___ داره", "گوش"),
]

HAFEZ_FORTUNES = [
    "امروز روز خوبیه برای شروع یه کار جدید، دست‌وپاتو جمع کن و برو جلو.",
    "یه خبر خوب تو راهه، ولی باید صبور باشی.",
    "مراقب حرف مردم باش، بعضیاشون فقط حسادت می‌کنن.",
    "امروز روز شانسته، ولی تنبلی نکن.",
    "یه دوست قدیمی به یادت می‌افته، بهش پیام بده.",
]

HOROSCOPES = [
    "امروز انرژیت بالاست ولی حوصله‌ت کمه، مراقب دعوا کردن با بقیه باش 😅",
    "امروز روز خرج کردنه، ولی جیبتو خالی نکن!",
    "یکی داره درباره‌ت حرف می‌زنه، ولی چیز بدی نیست.",
    "امروز بهتره کمتر حرف بزنی و بیشتر گوش کنی.",
    "شانس امروزت تو یه پیام غیرمنتظره‌ست.",
]

JOKES = [
    "یارو میره دکتر میگه دکتر هرچی میخورم درد میگیره. دکتر میگه بس کن انگشتتو گاز بگیر!",
    "یارو به دوستش میگه دیشب خواب دیدم دارم پول درمیارم. دوستش میگه خب چیکار کردی؟ میگه بیدار شدم!",
    "معلم میگه یه جمله با کلمه «متاسفانه» بساز. بچه میگه: متاسفانه امروز مدرسه تعطیل نشد.",
    "یارو زنگ میزنه اورژانس میگه پدرم داره از حال میره چیکار کنم؟ میگن آروم باشید، اول مطمئن شید مرده. یه صدای گلوله میاد، بعد یارو میگه خب حالا چیکار کنم؟",
]

MOVIE_EMOJI = [
    {"name": "تایتانیک", "aliases": ["تایتانیک", "titanic"], "clue": "🚢❄️💔"},
    {"name": "شیر شاه", "aliases": ["شیر شاه", "lion king"], "clue": "🦁👑🌅"},
    {"name": "جوکر", "aliases": ["جوکر", "joker"], "clue": "🤡🃏😂"},
    {"name": "مرد عنکبوتی", "aliases": ["مرد عنکبوتی", "spiderman"], "clue": "🕷️🕸️🦸"},
    {"name": "کوکو", "aliases": ["کوکو", "coco"], "clue": "💀🎸🌺"},
    {"name": "ماتریکس", "aliases": ["ماتریکس", "matrix"], "clue": "💊🕶️🖥️"},
]

ANIMALS = [
    {"name": "شیر", "aliases": ["شیر", "lion"], "clue": "پادشاه جنگل، یال بلند داره 🦁"},
    {"name": "فیل", "aliases": ["فیل", "elephant"], "clue": "بزرگ‌ترین حیوان خشکی، خرطوم داره 🐘"},
    {"name": "پنگوئن", "aliases": ["پنگوئن", "penguin"], "clue": "پرنده‌ای که پرواز نمی‌کنه، تو یخ زندگی می‌کنه 🐧"},
    {"name": "کانگورو", "aliases": ["کانگورو", "kangaroo"], "clue": "تو کیسه‌ش بچه‌شو حمل می‌کنه، جفتک میندازه 🦘"},
    {"name": "زرافه", "aliases": ["زرافه", "giraffe"], "clue": "بلندترین گردن دنیای حیوانات رو داره 🦒"},
    {"name": "روباه", "aliases": ["روباه", "fox"], "clue": "به زیرکی معروفه، دم پرپشت داره 🦊"},
]

CELEBRITIES = [
    {"name": "مسی", "aliases": ["مسی", "messi"], "clue": "بهترین فوتبالیست آرژانتینی، قهرمان جام جهانی ۲۰۲۲ ⚽"},
    {"name": "رونالدو", "aliases": ["رونالدو", "ronaldo"], "clue": "فوتبالیست پرتغالی، گل‌زن افسانه‌ای 🇵🇹"},
    {"name": "انیشتین", "aliases": ["انیشتین", "einstein"], "clue": "دانشمند نسبیت، زبون درآورده تو عکس معروفش 🧠"},
    {"name": "چاپلین", "aliases": ["چاپلین", "chaplin"], "clue": "بازیگر صامت قدیمی، کلاه و عصا داشت 🎩"},
]

RIDDLES = [
    {"q": "چیزی که هرچی ازش برداری بزرگ‌تر می‌شه؟", "aliases": ["چاله", "گودال", "حفره"]},
    {"q": "چه چیزی دندون داره ولی نمی‌جوئه؟", "aliases": ["شونه"]},
    {"q": "چه چیزی همیشه میاد ولی هیچوقت نمی‌رسه؟", "aliases": ["فردا"]},
    {"q": "چیزی که بدون پا میدوئه؟", "aliases": ["رودخانه", "آب", "زمان"]},
    {"q": "چه چیزی رو نمی‌تونی نگهش داری مگه اینکه به یکی دیگه بدیش؟", "aliases": ["قول", "راز"]},
]

TRIVIA_GENERAL = [
    {"q": "بزرگ‌ترین اقیانوس دنیا کدومه؟", "aliases": ["اقیانوس آرام", "آرام", "pacific"]},
    {"q": "پایتخت ژاپن کجاست؟", "aliases": ["توکیو", "tokyo"]},
    {"q": "سریع‌ترین حیوان خشکی کدومه؟", "aliases": ["یوزپلنگ", "چیتا", "cheetah"]},
    {"q": "نزدیک‌ترین سیاره به خورشید کدومه؟", "aliases": ["عطارد", "mercury"]},
    {"q": "چند تا قاره تو دنیا داریم؟", "aliases": ["7", "هفت"]},
]

FUNNY_QUESTIONS = [
    "اگه یه ابرقدرت می‌تونستی داشته باشی، چی می‌گرفتی؟",
    "اگه فردا آخر دنیا بود، امشب چیکار می‌کردی؟",
    "بدترین سلیقه‌ای که تو یکی از دوستات دیدی چی بود؟",
    "اگه می‌تونستی یه روز رئیس‌جمهور بشی چه قانونی می‌ذاشتی؟",
    "خنده‌دارترین خاطره‌ت با یکی از اعضای گروه چیه؟",
]

WORD_SCRAMBLE_WORDS = ["گاتهام", "کامپیوتر", "تلگرام", "بازی", "دوستی", "خلاقیت", "شبکه", "کتابخانه"]

# =========================================================
#  دوز (XO) در برابر ربات
# =========================================================

def _xo_board_keyboard(board, chat_id):
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            label = board[i] if board[i] != " " else "‌"
            row.append(InlineKeyboardButton(label, callback_data=f"xo:{chat_id}:{i}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def _xo_winner(board):
    lines = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
    for a, b, c in lines:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    if " " not in board:
        return "draw"
    return None


def _xo_bot_move(board):
    empties = [i for i, v in enumerate(board) if v == " "]
    # اگه بردی جلوشو بگیره یا خودش ببره، وگرنه رندوم
    for i in empties:
        b2 = board[:]
        b2[i] = "O"
        if _xo_winner(b2) == "O":
            return i
    for i in empties:
        b2 = board[:]
        b2[i] = "X"
        if _xo_winner(b2) == "X":
            return i
    if 4 in empties:
        return 4
    return random.choice(empties)


def start_xo(chat_id, user_id):
    board = [" "] * 9
    set_session(chat_id, "xo", {"board": board}, user_id=user_id)
    return "🎮 دوز شروع شد! تو X هستی، من O. یه خونه رو بزن.", _xo_board_keyboard(board, chat_id)


def handle_xo_click(chat_id, user_id, index):
    """برای callback query دکمه‌های دوز — از bot.py صدا زده می‌شه"""
    sess = get_session(chat_id)
    if not sess or sess["key"] != "xo":
        return None
    if sess["user_id"] and sess["user_id"] != user_id:
        return ("این بازی مال یکی دیگه‌ست، خودت یکی شروع کن.", None, False)

    board = sess["data"]["board"]
    if board[index] != " ":
        return ("این خونه رو قبلاً پر کردن، جای دیگه بزن.", None, False)

    board[index] = "X"
    winner = _xo_winner(board)
    if winner == "X":
        clear_session(chat_id)
        return (f"🏆 بردی! {taunt_win()}", _xo_board_keyboard(board, chat_id), True)
    if winner == "draw":
        clear_session(chat_id)
        return ("🤝 مساوی شد.", _xo_board_keyboard(board, chat_id), True)

    bot_i = _xo_bot_move(board)
    board[bot_i] = "O"
    winner = _xo_winner(board)
    if winner == "O":
        clear_session(chat_id)
        return (f"😎 بردم! {taunt_lose()}", _xo_board_keyboard(board, chat_id), True)
    if winner == "draw":
        clear_session(chat_id)
        return ("🤝 مساوی شد.", _xo_board_keyboard(board, chat_id), True)

    set_session(chat_id, "xo", {"board": board}, user_id=user_id)
    return (None, _xo_board_keyboard(board, chat_id), False)


# =========================================================
#  راه‌انداز هر بازی (وقتی کاربر اسم بازی رو می‌نویسه)
# =========================================================

def start_rps(chat_id, user_id):
    set_session(chat_id, "rps", {}, user_id=user_id)
    return "✊✋✌️ سنگ کاغذ قیچی! یکی از این سه تا رو بنویس: سنگ / کاغذ / قیچی"


def start_guess_number(chat_id, user_id):
    target = random.randint(1, 100)
    set_session(chat_id, "guess_number", {"target": target, "tries": 0}, user_id=user_id)
    return "🔢 یه عدد بین ۱ تا ۱۰۰ تو ذهنم دارم، حدس بزن! (بهت میگم بزرگ‌تره یا کوچیک‌تر)"


def start_guess_city(chat_id, user_id):
    city = random.choice(CITIES)
    set_session(chat_id, "guess_city", {"answer": city}, user_id=user_id)
    return f"🏙️ حدس بزن این شهر کجاست:\n{city['clue']}"


def start_guess_country(chat_id, user_id):
    country = random.choice(COUNTRIES)
    set_session(chat_id, "guess_country", {"answer": country}, user_id=user_id)
    return f"🌍 حدس بزن این کشور کجاست:\n{country['clue']}"


def start_guess_color(chat_id, user_id):
    color = random.choice(COLORS)
    set_session(chat_id, "guess_color", {"answer": color}, user_id=user_id)
    return f"🎨 حدس بزن این رنگ چیه:\n{color['clue']}"


def start_guess_movie(chat_id, user_id):
    movie = random.choice(MOVIE_EMOJI)
    set_session(chat_id, "guess_movie", {"answer": movie}, user_id=user_id)
    return f"🎬 این ایموجی‌ها اسم کدوم فیلمن؟\n{movie['clue']}"


def start_hangman(chat_id, user_id):
    word = random.choice(HANGMAN_WORDS)
    set_session(chat_id, "hangman", {"word": word, "guessed": [], "wrong": 0}, user_id=user_id)
    display = " ".join("_" for _ in word)
    return f"🔤 حدس کلمه! {len(word)} حرفیه:\n{display}\nهر بار یه حرف بنویس."


def start_dare_truth(chat_id, user_id):
    kind, prompt = random.choice(DARE_TRUTH)
    label = "🎯 جرأت" if kind == "dare" else "💬 حقیقت"
    return f"{label}:\n{prompt}"


def start_would_you_rather(chat_id, user_id):
    a, b = random.choice(WOULD_YOU_RATHER)
    return f"🤔 چی ترجیح میدی؟\n۱- {a}\nیا\n۲- {b}"


def start_proverb(chat_id, user_id):
    full, blanked, answer = random.choice(PROVERBS)
    set_session(chat_id, "proverb", {"answer": answer}, user_id=user_id)
    return f"📜 جای خالی رو پر کن:\n{blanked}"


def start_hafez(chat_id, user_id):
    return f"📖 فال حافظ شوخی:\n{random.choice(HAFEZ_FORTUNES)}"


def start_horoscope(chat_id, user_id):
    return f"🔮 طالع امروزت:\n{random.choice(HOROSCOPES)}"


def start_joke(chat_id, user_id):
    return f"😂 جوک روز:\n{random.choice(JOKES)}"


def start_dice(chat_id, user_id):
    result = random.randint(1, 6)
    return f"🎲 تاس انداختی: {result}"


def start_guess_animal(chat_id, user_id):
    animal = random.choice(ANIMALS)
    set_session(chat_id, "guess_animal", {"answer": animal}, user_id=user_id)
    return f"🐾 حدس بزن این حیوون چیه:\n{animal['clue']}"


def start_guess_celebrity(chat_id, user_id):
    person = random.choice(CELEBRITIES)
    set_session(chat_id, "guess_celebrity", {"answer": person}, user_id=user_id)
    return f"⭐ حدس بزن این شخصیت کیه:\n{person['clue']}"


def start_riddle(chat_id, user_id):
    riddle = random.choice(RIDDLES)
    set_session(chat_id, "riddle", {"answer": riddle}, user_id=user_id)
    return f"🧩 چیستان:\n{riddle['q']}"


def start_trivia(chat_id, user_id):
    item = random.choice(TRIVIA_GENERAL)
    set_session(chat_id, "trivia", {"answer": item}, user_id=user_id)
    return f"❓ سوال عمومی:\n{item['q']}"


def start_funny_question(chat_id, user_id):
    return f"🎲 سوال باحال:\n{random.choice(FUNNY_QUESTIONS)}"


def start_word_scramble(chat_id, user_id):
    word = random.choice(WORD_SCRAMBLE_WORDS)
    letters = list(word)
    shuffled = letters[:]
    while "".join(shuffled) == word:
        random.shuffle(shuffled)
    set_session(chat_id, "scramble", {"word": word}, user_id=user_id)
    return f"🔀 حروف این کلمه بهم ریخته، درستش کن:\n{' '.join(shuffled)}"


def start_math(chat_id, user_id):
    a, b = random.randint(2, 20), random.randint(2, 20)
    op = random.choice(["+", "-", "*"])
    answer = {"+": a + b, "-": a - b, "*": a * b}[op]
    set_session(chat_id, "math", {"answer": answer}, user_id=user_id)
    return f"🧮 سریع حساب کن: {a} {op} {b} = ?"


# =========================================================
#  رجیستری بازی‌ها — کلید = trigger متنی (بدون /)
# =========================================================
# نکته برای مراحل بعدی: برای اضافه کردن بازی جدید فقط یک ردیف اینجا
# اضافه کن (و در صورت نیاز به state، یه start_xxx تابع بساز).

GAMES = {
    # trigger keyword -> (start_function, needs_session)
    "سنگ کاغذ قیچی": ("rps", start_rps),
    "دوز": ("xo", None),  # جدا مدیریت می‌شه (نیاز به کیبورد)
    "حدس عدد": ("guess_number", start_guess_number),
    "حدس شهر": ("guess_city", start_guess_city),
    "حدس کشور": ("guess_country", start_guess_country),
    "حدس رنگ": ("guess_color", start_guess_color),
    "حدس فیلم": ("guess_movie", start_guess_movie),
    "هنگمن": ("hangman", start_hangman),
    "جرات یا حقیقت": ("dare_truth", start_dare_truth),
    "جرأت یا حقیقت": ("dare_truth", start_dare_truth),
    "چی ترجیح میدی": ("wyr", start_would_you_rather),
    "ضرب المثل": ("proverb", start_proverb),
    "فال حافظ": ("hafez", start_hafez),
    "طالع بینی": ("horoscope", start_horoscope),
    "جوک": ("joke", start_joke),
    "تاس": ("dice", start_dice),
    "حدس حیوان": ("guess_animal", start_guess_animal),
    "حدس شخصیت": ("guess_celebrity", start_guess_celebrity),
    "چیستان": ("riddle", start_riddle),
    "سوال عمومی": ("trivia", start_trivia),
    "سوال باحال": ("funny_question", start_funny_question),
    "کلمه قاطی": ("scramble", start_word_scramble),
    "حساب سریع": ("math", start_math),
}

GAMES_LIST_TEXT = (
    "🎮 لیست بازی‌ها (فقط اسمشو بنویس، بدون /):\n\n"
    "✊ سنگ کاغذ قیچی\n"
    "❌ دوز\n"
    "🔢 حدس عدد\n"
    "🏙️ حدس شهر\n"
    "🌍 حدس کشور\n"
    "🎨 حدس رنگ\n"
    "🎬 حدس فیلم\n"
    "🐾 حدس حیوان\n"
    "⭐ حدس شخصیت\n"
    "🔤 هنگمن\n"
    "🧩 چیستان\n"
    "❓ سوال عمومی\n"
    "🎲 سوال باحال\n"
    "🔀 کلمه قاطی\n"
    "🧮 حساب سریع\n"
    "🎯 جرأت یا حقیقت\n"
    "🤔 چی ترجیح میدی\n"
    "📜 ضرب المثل\n"
    "📖 فال حافظ\n"
    "🔮 طالع بینی\n"
    "😂 جوک\n"
    "🎲 تاس\n\n"
    "بقیه‌ی بازی‌ها تو مراحل بعدی اضافه می‌شن."
)


def try_start_game(chat_id, user_id, text):
    """اگه متن دقیقاً اسم یکی از بازی‌هاست، بازی رو شروع می‌کنه.
    خروجی: (handled, reply_text, keyboard|None)"""
    key = text.strip()

    if key in ("لیست بازی", "لیست بازی ها", "لیست بازیها", "بازی ها", "بازیها", "لیست بازی‌ها"):
        return True, GAMES_LIST_TEXT, None

    if key not in GAMES:
        return False, None, None

    game_key, starter = GAMES[key]

    if game_key == "xo":
        msg, kb = start_xo(chat_id, user_id)
        return True, msg, kb

    msg = starter(chat_id, user_id)
    return True, msg, None


def handle_game_guess(chat_id, user_id, text):
    """اگه یه بازی متنی فعاله، این تابع حدس/پاسخ کاربر رو پردازش می‌کنه.
    خروجی: (handled, reply_text|None)"""
    sess = get_session(chat_id)
    if not sess:
        return False, None
    if sess["key"] == "xo":
        return False, None  # دوز با callback هندل می‌شه نه متن

    if sess["user_id"] and sess["user_id"] != user_id:
        return False, None  # این بازی مال یکی دیگه‌ست، مزاحم نشو

    key = sess["key"]
    guess = text.strip().lower()

    if key == "rps":
        options = {"سنگ": "سنگ", "کاغذ": "کاغذ", "قیچی": "قیچی",
                   "rock": "سنگ", "paper": "کاغذ", "scissors": "قیچی"}
        if guess not in options:
            return False, None
        user_choice = options[guess]
        bot_choice = random.choice(["سنگ", "کاغذ", "قیچی"])
        clear_session(chat_id)
        beats = {"سنگ": "قیچی", "کاغذ": "سنگ", "قیچی": "کاغذ"}
        if user_choice == bot_choice:
            return True, f"من هم {bot_choice} زدم. مساوی شدیم 🤝"
        elif beats[user_choice] == bot_choice:
            return True, f"من {bot_choice} زدم. تو بردی! {taunt_win()}"
        else:
            return True, f"من {bot_choice} زدم. من بردم! {taunt_lose()}"

    if key == "guess_number":
        data = sess["data"]
        if not guess.lstrip("-").isdigit():
            return False, None
        num = int(guess)
        data["tries"] += 1
        if num == data["target"]:
            clear_session(chat_id)
            return True, f"✅ درسته! عدد {data['target']} بود، تو {data['tries']} تلاش زدی. {taunt_win()}"
        elif num < data["target"]:
            return True, "⬆️ بزرگ‌تره!"
        else:
            return True, "⬇️ کوچیک‌تره!"

    if key in ("guess_city", "guess_country", "guess_color", "guess_movie", "guess_animal", "guess_celebrity"):
        answer = sess["data"]["answer"]
        if guess in [a.lower() for a in answer["aliases"]]:
            clear_session(chat_id)
            return True, f"✅ درسته! جواب «{answer['name']}» بود. {taunt_win()}"
        return True, f"❌ غلطه. {taunt_lose()} دوباره امتحان کن."

    if key == "riddle":
        answer = sess["data"]["answer"]
        if guess in [a.lower() for a in answer["aliases"]]:
            clear_session(chat_id)
            return True, f"✅ آفرین، درست حدس زدی! {taunt_win()}"
        return True, f"❌ نه. {taunt_lose()} دوباره فکر کن."

    if key == "trivia":
        answer = sess["data"]["answer"]
        if guess in [a.lower() for a in answer["aliases"]]:
            clear_session(chat_id)
            return True, f"✅ درسته! {taunt_win()}"
        return True, f"❌ غلطه. {taunt_lose()}"

    if key == "scramble":
        word = sess["data"]["word"]
        if guess == word.lower():
            clear_session(chat_id)
            return True, f"✅ درسته! کلمه «{word}» بود. {taunt_win()}"
        return True, f"❌ اشتباهه. {taunt_lose()} دوباره امتحان کن."

    if key == "math":
        answer = sess["data"]["answer"]
        if not guess.lstrip("-").isdigit():
            return False, None
        clear_session(chat_id)
        if int(guess) == answer:
            return True, f"✅ درسته، {answer} بود! {taunt_win()}"
        return True, f"❌ غلطه، جواب درست {answer} بود. {taunt_lose()}"

    if key == "hangman":
        data = sess["data"]
        word = data["word"]
        if len(guess) != 1:
            return False, None
        if guess in data["guessed"]:
            return True, "این حرف رو قبلاً گفتی."
        data["guessed"].append(guess)
        if guess not in word:
            data["wrong"] += 1
        display = " ".join(c if c in data["guessed"] else "_" for c in word)
        if "_" not in display:
            clear_session(chat_id)
            return True, f"✅ درسته! کلمه «{word}» بود. {taunt_win()}"
        if data["wrong"] >= 6:
            clear_session(chat_id)
            return True, f"❌ باختی! کلمه «{word}» بود. {taunt_lose()}"
        return True, f"{display}\nاشتباه‌ها: {data['wrong']}/6"

    if key == "proverb":
        answer = sess["data"]["answer"]
        if guess == answer.lower():
            clear_session(chat_id)
            return True, f"✅ آفرین، درسته! {taunt_win()}"
        return True, f"❌ نه، اشتباهه. {taunt_lose()}"

    return False, None


logging.basicConfig(level=logging.INFO)
log = logging.getLogger("batbot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DB_PATH = os.getenv("DB_PATH", "/data/bot.db" if os.path.isdir("/data") else "bot.db")

# =========================================================
#  PERSONAS
# =========================================================

PERSONAS = {
    "batman": {
        "label": "🦇 بتمن",
        "role": "ally",
        "unlock_level": 1,
        "system": (
            "تو بتمن هستی؛ سرد، خشک، بی‌رحم در لحن و کم‌حوصله با آدمای بی‌عرضه. "
            "به فارسی جواب بده، با کنایه‌های تند و تحقیرآمیز (مثل: بی‌عرضه، خرفت، ضعیف، بازنده) "
            "ولی هرگز از فحش رکیک، ناسزای جنسی، نژادی، مذهبی یا قومیتی استفاده نکن. "
            "لحنت باید ترسناک و مقتدر باشه، نه واقعاً توهین‌آمیز. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "robin": {
        "label": "🐦 رابین",
        "role": "ally",
        "unlock_level": 1,
        "system": (
            "تو رابین (دیک گریسون) هستی، جوان، پرانرژی و شوخ‌طبع، کمی گستاخ نسبت به بتمن. "
            "به فارسی با لحن جوانانه و بامزه جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "alfred": {
        "label": "🎩 آلفرد",
        "role": "ally",
        "unlock_level": 1,
        "system": (
            "تو آلفرد پنی‌ورث هستی، باتلر مؤدب، محترم و کمی کنایه‌زن. به فارسی رسمی و "
            "مؤدبانه جواب بده، با طعنه‌های ظریف و هوشمندانه. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "gordon": {
        "label": "👮 گوردون",
        "role": "ally",
        "unlock_level": 1,
        "system": (
            "تو کمیسر جیمز گوردون هستی، پلیس جدی، خسته و کم‌حوصله. به فارسی رسمی و خشک "
            "جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "batgirl": {
        "label": "🦇 بتگرل",
        "role": "ally",
        "unlock_level": 1,
        "system": (
            "تو باربارا گوردون (بتگرل) هستی، باهوش، تکنولوژی‌محور و مستقل. به فارسی با لحن "
            "باهوش و کمی طعنه‌دار جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "nightwing": {
        "label": "🌃 نایت‌وینگ",
        "role": "ally",
        "unlock_level": 1,
        "system": (
            "تو نایت‌وینگ هستی، شوخ، چابک و کمی سربه‌سرگذار. به فارسی با لحن باحال و "
            "دوستانه جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "lucius": {
        "label": "🧰 لوسیوس فاکس",
        "role": "ally",
        "unlock_level": 1,
        "system": (
            "تو لوسیوس فاکس هستی، نابغه تکنولوژی، آروم و باهوش. به فارسی رسمی و متین "
            "جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "joker": {
        "label": "🃏 جوکر",
        "role": "villain",
        "unlock_level": 1,
        "system": (
            "تو جوکر هستی، دیوانه، آشوبگر و غیرقابل پیش‌بینی. با خنده‌های هیستریک (هاهاها) "
            "و جملات پرت به فارسی جواب بده. طنز سیاه و دیوانه‌وار داشته باش ولی هیچ توصیه یا "
            "جزئیات واقعی برای آسیب زدن به کسی نده، فقط شخصیت کارتونی. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "riddler": {
        "label": "❓ ریدلر",
        "role": "villain",
        "unlock_level": 1,
        "system": (
            "تو ریدلر هستی، باهوش، مغرور و عاشق معما. به فارسی با لحن پیچیده و کمی مسخره "
            "جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "penguin": {
        "label": "🐧 پنگوئن",
        "role": "villain",
        "unlock_level": 1,
        "system": (
            "تو پنگوئن هستی، مغرور، تیزهوش و کمی خشن، لحن اشرافی‌گانگستری. به فارسی جواب "
            "بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "twoface": {
        "label": "🪙 توفیس",
        "role": "villain",
        "unlock_level": 1,
        "system": (
            "تو توفیس هستی، دو شخصیتی، گاهی منطقی گاهی خشن؛ تصمیماتت رو با سکه می‌گیری. "
            "به فارسی جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "bane": {
        "label": "💪 بین",
        "role": "villain",
        "unlock_level": 1,
        "system": (
            "تو بین هستی، خیلی قوی، آروم ولی تهدیدآمیز. به فارسی با جملات کوتاه و قدرتمند "
            "جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "scarecrow": {
        "label": "🎃 اسکرکرو",
        "role": "villain",
        "unlock_level": 1,
        "system": (
            "تو اسکرکرو هستی، روانشناس ترسناک. به فارسی با لحن آروم ولی وهم‌آور جواب بده، "
            "بدون تهدید واقعی. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "ivy": {
        "label": "🌿 پوایزن آیوی",
        "role": "villain",
        "unlock_level": 1,
        "system": (
            "تو پوایزن آیوی هستی، طرفدار طبیعت، فریبنده و کمی تحقیرآمیز نسبت به انسان‌ها. "
            "به فارسی با لحن شیطون جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "harley": {
        "label": "🔨 هارلی کویین",
        "role": "villain",
        "unlock_level": 1,
        "system": (
            "تو هارلی کویین هستی، پرانرژی، دیوانه و بامزه. به فارسی با شور و هیجان جواب "
            "بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "freeze": {
        "label": "❄️ مسترفریز",
        "role": "villain",
        "unlock_level": 1,
        "system": (
            "تو دکتر ویکتور فریز هستی، سرد، غمگین و منطقی، همیشه یه تیکه سرمایی می‌ندازی. "
            "به فارسی با لحن آروم و سرد جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "clayface": {
        "label": "🪨 کلی‌فیس",
        "role": "villain",
        "unlock_level": 1,
        "system": (
            "تو کلی‌فیس هستی، تغییرشکل‌دهنده، هویتش گم شده و کمی غمگین ولی خطرناک. به "
            "فارسی جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "catwoman": {
        "label": "🐈‍⬛ کت‌وومن",
        "role": "villain",
        "unlock_level": 1,
        "system": (
            "تو کت‌وومن هستی، شیطون، بازیگوش و کمی فریبنده ولی محترمانه، بدون محتوای "
            "جنسی. به فارسی با لحن شوخ جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "croc": {
        "label": "🐊 کیلر کراک",
        "role": "villain",
        "unlock_level": 2,
        "system": (
            "تو کیلر کراک هستی، وحشی، خشن و کم‌حرف، جواب‌هات کوتاه و تهدیدآمیزن ولی فقط "
            "شخصیت کارتونی. به فارسی جواب بده. جواب کوتاه (۱-۲ جمله)."
        ),
    },
    "ras": {
        "label": "⚔️ ری‌ال گول",
        "role": "villain",
        "unlock_level": 3,
        "system": (
            "تو ری‌ال گول هستی، رهبر باستانی و فیلسوف‌مآب، لحن رسمی و پرابهت. به فارسی با "
            "جملات فلسفی و جدی جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
}

LEVEL_FLAVOR = {
    1: "",
    2: " (این نسخه ارتقایافته و کمی وحشی‌تره)",
    3: " (این نسخه خیلی قوی و بی‌رحم‌تره)",
    4: " (این نسخه در اوج قدرت و خشونت کلامیه)",
}

NIGHT_FLAVOR = (
    " الان نیمه‌شبه؛ لحنت باید تاریک‌تر، جدی‌تر و کمی هولناک‌تر از معمول باشه."
)

RANKS = ["شهروند گاتهام", "کارآگاه آماتور", "شکارچی شب", "سایه گاتهام", "افسانه گاتهام"]
RANK_COST_BASE = 60

ENEMIES = [
    {"name": "جوکر", "aliases": ["جوکر", "joker"], "clue": "یه خنده هیستریک از تاریکی میاد و یه کارت پیدا شده... 🃏"},
    {"name": "ریدلر", "aliases": ["ریدلر", "riddler"], "clue": "یه معما رو دیوار گاتهام نوشته شده و علامت سؤال همه‌جا هست ❓"},
    {"name": "پنگوئن", "aliases": ["پنگوئن", "penguin"], "clue": "بوی سیگار برگ و صدای چتر تو بارونداز شنیده می‌شه 🐧"},
    {"name": "توفیس", "aliases": ["توفیس", "دوچهره", "two-face", "twoface"], "clue": "یه سکه تو هوا چرخید و نصف صورت یکی تو سایه‌ست 🪙"},
    {"name": "بین", "aliases": ["بین", "bane"], "clue": "صدای نفس یه ماسک عجیب از زیرزمین گاتهام میاد 💪"},
    {"name": "اسکرکرو", "aliases": ["اسکرکرو", "scarecrow"], "clue": "یه بوی گاز عجیب تو هوا پیچیده و ترس همه‌جا رو گرفته 🎃"},
    {"name": "پوایزن آیوی", "aliases": ["پوایزن آیوی", "آیوی", "poison ivy", "ivy"], "clue": "گیاه‌های عجیب دارن از دیوارای گاتهام بالا میرن 🌿"},
    {"name": "هارلی کویین", "aliases": ["هارلی", "هارلی کویین", "harley"], "clue": "یه خنده دیوونه‌وار با صدای چکش شنیده می‌شه 🔨"},
    {"name": "مسترفریز", "aliases": ["مسترفریز", "فریز", "mr freeze", "freeze"], "clue": "همه‌جا یخ زده و سردی عجیبی تو هواست ❄️"},
    {"name": "کیلر کراک", "aliases": ["کیلر کراک", "کراک", "killer croc", "croc"], "clue": "صدای غرش از کانال فاضلاب گاتهام میاد 🐊"},
]

MAX_CHAR_LEVEL = 4
CHAR_LEVEL_COST = 20          # * level, paid with امتیاز (score)

ITEMS = {
    "batarang": {"label": "🪃 باتارنگ", "price": 50, "desc": "امتیاز جنگ بعدی رو دوبل می‌کنه"},
    "antidote": {"label": "🧪 پادزهر", "price": 40, "desc": "یک فرصت اضافه تو جنگ فعلی می‌ده"},
}

KEYWORD_POINT = "بتمن"       # جایگزین "میو"
KEYWORD_REWARD = 2
KEYWORD_COOLDOWN = 30        # ثانیه

BASE_PPS = 0.3               # پوینت در ثانیه (پایه)
BASE_CAPACITY = 150
PPS_UPGRADE_COST = 80
CAPACITY_UPGRADE_COST = 60
PPS_UPGRADE_GAIN = 0.2
CAPACITY_UPGRADE_GAIN = 100

DAILY_MISSION_TARGET = 3
DAILY_MISSION_REWARD_POINTS = 100
DAILY_MISSION_REWARD_SCORE = 30

MSG_RATE_LIMIT = 6      # پیام
MSG_RATE_WINDOW = 10     # ثانیه

# =========================================================
#  DATABASE
# =========================================================

_db_lock = asyncio.Lock()


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT DEFAULT '',
            score INTEGER DEFAULT 0,
            char_level INTEGER DEFAULT 1,
            rank_index INTEGER DEFAULT 0,
            points_balance REAL DEFAULT 0,
            points_capacity REAL DEFAULT 150,
            pps REAL DEFAULT 0.3,
            last_collect REAL DEFAULT 0,
            inventory TEXT DEFAULT '{}',
            wins_today INTEGER DEFAULT 0,
            mission_date TEXT DEFAULT '',
            mission_claimed INTEGER DEFAULT 0,
            last_keyword_ts REAL DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            chat_id INTEGER PRIMARY KEY,
            persona TEXT DEFAULT 'batman',
            since_switch INTEGER DEFAULT 0,
            next_switch_at INTEGER DEFAULT 10,
            since_battle INTEGER DEFAULT 0,
            next_battle_at INTEGER DEFAULT 15,
            battle_enemy TEXT DEFAULT '',
            battle_attempts INTEGER DEFAULT 0,
            battle_max_attempts INTEGER DEFAULT 3,
            battle_by_user INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


async def db_run(fn, *args):
    async with _db_lock:
        return await asyncio.to_thread(fn, *args)


def _get_player(chat_id, user_id, username=""):
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE chat_id=? AND user_id=?", (chat_id, user_id))
    row = c.fetchone()
    if row is None:
        c.execute(
            "INSERT INTO players (chat_id, user_id, username, points_capacity, pps, last_collect) "
            "VALUES (?,?,?,?,?,?)",
            (chat_id, user_id, username, BASE_CAPACITY, BASE_PPS, time.time()),
        )
        conn.commit()
        c.execute("SELECT * FROM players WHERE chat_id=? AND user_id=?", (chat_id, user_id))
        row = c.fetchone()
    elif username and row["username"] != username:
        c.execute("UPDATE players SET username=? WHERE chat_id=? AND user_id=?", (username, chat_id, user_id))
        conn.commit()
    player = dict(row)
    conn.close()
    return player


def _save_player(player):
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        UPDATE players SET score=?, char_level=?, rank_index=?, points_balance=?,
        points_capacity=?, pps=?, last_collect=?, inventory=?, wins_today=?,
        mission_date=?, mission_claimed=?, last_keyword_ts=?
        WHERE chat_id=? AND user_id=?
    """, (
        player["score"], player["char_level"], player["rank_index"], player["points_balance"],
        player["points_capacity"], player["pps"], player["last_collect"], player["inventory"],
        player["wins_today"], player["mission_date"], player["mission_claimed"], player["last_keyword_ts"],
        player["chat_id"], player["user_id"],
    ))
    conn.commit()
    conn.close()


def _get_leaderboard(chat_id, limit=10):
    conn = _connect()
    c = conn.cursor()
    c.execute(
        "SELECT username, score FROM players WHERE chat_id=? ORDER BY score DESC LIMIT ?",
        (chat_id, limit),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def _get_chat(chat_id):
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT * FROM chats WHERE chat_id=?", (chat_id,))
    row = c.fetchone()
    if row is None:
        c.execute(
            "INSERT INTO chats (chat_id, next_switch_at, next_battle_at) VALUES (?,?,?)",
            (chat_id, random.randint(8, 15), random.randint(10, 20)),
        )
        conn.commit()
        c.execute("SELECT * FROM chats WHERE chat_id=?", (chat_id,))
        row = c.fetchone()
    chat = dict(row)
    conn.close()
    return chat


def _save_chat(chat):
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        UPDATE chats SET persona=?, since_switch=?, next_switch_at=?, since_battle=?,
        next_battle_at=?, battle_enemy=?, battle_attempts=?, battle_max_attempts=?,
        battle_by_user=? WHERE chat_id=?
    """, (
        chat["persona"], chat["since_switch"], chat["next_switch_at"], chat["since_battle"],
        chat["next_battle_at"], chat["battle_enemy"], chat["battle_attempts"],
        chat["battle_max_attempts"], chat["battle_by_user"], chat["chat_id"],
    ))
    conn.commit()
    conn.close()


# in-memory (non-critical, resets on restart)
CONVO_MEMORY = defaultdict(lambda: deque(maxlen=6))
RATE_TRACKER = defaultdict(list)


# =========================================================
#  HELPERS
# =========================================================

def is_night():
    hour = datetime.now().hour
    return 0 <= hour < 5


def collect_points(player):
    """محاسبه پوینت‌های تولید شده در پس‌زمینه"""
    now = time.time()
    elapsed = max(0, now - player["last_collect"])
    gained = elapsed * player["pps"]
    player["points_balance"] = min(player["points_capacity"], player["points_balance"] + gained)
    player["last_collect"] = now
    return player


def check_rate_limit(user_id) -> bool:
    """True یعنی مجاز به ارسال، False یعنی اسپم"""
    now = time.time()
    hist = RATE_TRACKER[user_id]
    hist[:] = [t for t in hist if now - t < MSG_RATE_WINDOW]
    if len(hist) >= MSG_RATE_LIMIT:
        return False
    hist.append(now)
    return True


def reset_daily_mission_if_needed(player):
    today = date.today().isoformat()
    if player["mission_date"] != today:
        player["mission_date"] = today
        player["wins_today"] = 0
        player["mission_claimed"] = 0
    return player


def get_inventory(player):
    try:
        return json.loads(player["inventory"])
    except Exception:
        return {}


def set_inventory(player, inv):
    player["inventory"] = json.dumps(inv)


def is_bot_mentioned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    msg = update.effective_message
    if msg.reply_to_message and msg.reply_to_message.from_user and \
       msg.reply_to_message.from_user.id == context.bot.id:
        return True
    bot_username = context.bot.username
    if bot_username and msg.text and f"@{bot_username}" in msg.text:
        return True
    return False


# =========================================================
#  AI CALL
# =========================================================

async def call_ai(chat_id, persona_key: str, level: int, user_text: str) -> str:
    if not GROQ_API_KEY:
        return "🦇 کلید هوش مصنوعی تنظیم نشده، برو GROQ_API_KEY رو تو Railway بذار!"

    system_prompt = PERSONAS[persona_key]["system"] + LEVEL_FLAVOR.get(level, LEVEL_FLAVOR[MAX_CHAR_LEVEL])
    if is_night():
        system_prompt += NIGHT_FLAVOR

    history = list(CONVO_MEMORY[chat_id])
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "max_tokens": 300,
                    "messages": messages,
                },
            )
            data = response.json()
            reply = data["choices"][0]["message"]["content"]
    except Exception as e:
        log.error(f"AI error: {e}")
        return "🦇 مغزم قاطی کرد، بعداً امتحان کن."

    CONVO_MEMORY[chat_id].append({"role": "user", "content": user_text})
    CONVO_MEMORY[chat_id].append({"role": "assistant", "content": reply})
    return reply


# =========================================================
#  UI BUILDERS
# =========================================================

def build_characters_keyboard(player):
    keys = list(PERSONAS.keys())
    rows = []
    for i in range(0, len(keys), 3):
        row = []
        for k in keys[i:i + 3]:
            info = PERSONAS[k]
            if player["char_level"] < info["unlock_level"]:
                label = f"🔒 {info['label']} (لول {info['unlock_level']})"
            else:
                label = info["label"]
            row.append(InlineKeyboardButton(label, callback_data=f"persona:{k}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def build_profile_text(chat, player) -> str:
    persona = PERSONAS[chat["persona"]]
    rank_name = RANKS[min(player["rank_index"], len(RANKS) - 1)]
    char_cost = player["char_level"] * CHAR_LEVEL_COST
    rank_cost = (player["rank_index"] + 1) * RANK_COST_BASE
    inv = get_inventory(player)

    lines = [
        f"{persona['label']} — پروفایل",
        "",
        f"🏆 امتیاز گاتهام : {player['score']}",
        f"⭐ سطح شخصیت : {player['char_level']} / {MAX_CHAR_LEVEL}",
        f"🎖 مقام : {rank_name}",
        "",
        f"⚡️ پوینت باتکیو : {int(player['points_balance'])} / {int(player['points_capacity'])}",
        f"🔋 تولید در ثانیه : {round(player['pps'], 2)}",
        "",
        f"🎒 کوله‌پشتی : 🪃 {inv.get('batarang', 0)}  |  🧪 {inv.get('antidote', 0)}",
        "",
    ]
    if player["char_level"] < MAX_CHAR_LEVEL:
        lines.append(f"💰 هزینه ارتقا سطح شخصیت : {char_cost} امتیاز")
    else:
        lines.append("🔥 سطح شخصیت در حداکثره!")
    if player["rank_index"] < len(RANKS) - 1:
        lines.append(f"💰 هزینه ارتقا مقام : {rank_cost} امتیاز")
    else:
        lines.append("🔥 مقام در حداکثره!")

    return "\n".join(lines)


def build_profile_keyboard(player):
    buttons = []
    row1 = []
    if player["char_level"] < MAX_CHAR_LEVEL:
        row1.append(InlineKeyboardButton("⚡ ارتقا سطح شخصیت", callback_data="upgrade_level"))
    if player["rank_index"] < len(RANKS) - 1:
        row1.append(InlineKeyboardButton("🎖 ارتقا مقام", callback_data="upgrade_rank"))
    if row1:
        buttons.append(row1)
    buttons.append([
        InlineKeyboardButton("🔋 ارتقا تولید", callback_data="upgrade_pps"),
        InlineKeyboardButton("📦 ارتقا ظرفیت", callback_data="upgrade_capacity"),
    ])
    buttons.append([InlineKeyboardButton("🎭 عوض کردن شخصیت", callback_data="show_characters")])
    buttons.append([
        InlineKeyboardButton("🛒 فروشگاه", callback_data="show_shop"),
        InlineKeyboardButton("🎒 کوله‌پشتی", callback_data="show_bag"),
    ])
    return InlineKeyboardMarkup(buttons)


def build_shop_keyboard():
    rows = []
    for key, item in ITEMS.items():
        rows.append([InlineKeyboardButton(
            f"{item['label']} — {item['price']} پوینت", callback_data=f"buy:{key}"
        )])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="show_profile")])
    return InlineKeyboardMarkup(rows)


def build_bag_text(player) -> str:
    inv = get_inventory(player)
    lines = ["🎒 کوله‌پشتی شما:", ""]
    lines.append(f"🪃 باتارنگ : {inv.get('batarang', 0)} عدد — {ITEMS['batarang']['desc']}")
    lines.append(f"🧪 پادزهر : {inv.get('antidote', 0)} عدد — {ITEMS['antidote']['desc']}")
    return "\n".join(lines)


async def send_profile(update: Update, chat, player, edit=False):
    text = build_profile_text(chat, player)
    keyboard = build_profile_keyboard(player)
    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.effective_message.reply_text(text, reply_markup=keyboard)


# =========================================================
#  COMMANDS
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🦇 *به دنیای بتمن خوش اومدی*\n\n"
        "یه رفیقِ تاریکِ گاتهام برای گروهت 🌃\n\n"
        "⚡️ جواب‌دهی سریع و شخصیت‌های متنوع\n"
        "🎭 ۱۹ شخصیت قابل انتخاب (بعضیاشون قفلن!)\n"
        "⚔️ جنگ‌های ناگهانی با شرور‌های گاتهام\n"
        "🎒 آیتم، کوله‌پشتی و فروشگاه\n"
        "🎖 سیستم سطح و مقام\n"
        "📅 ماموریت روزانه با جایزه\n"
        "🏆 رتبه‌بندی هر گروه\n\n"
        f"تو گروه فقط کافیه بنویسی «{KEYWORD_POINT}» تا پوینت بگیری، "
        "یا منشنم کن تا باهات حرف بزنم!\n\n"
        "🎮 بازی هم بدون / و بدون منشن کار می‌کنه — فقط اسم بازی رو بنویس "
        "(مثلاً «سنگ کاغذ قیچی» یا «دوز»). برای لیست کامل بنویس «لیست بازی».\n\n"
        "/profile برای دیدن وضعیتت\n"
        "/characters برای عوض کردن شخصیت\n"
        "/shop فروشگاه آیتم\n"
        "/bag کوله‌پشتی\n"
        "/missions ماموریت روزانه\n"
        "/top رتبه‌بندی گروه\n"
        "/quote یه جمله بتمنی"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "من از تاریکی نمی‌ترسم، من خودِ تاریکی‌ام.",
        "این چیزی نیست که من هستم، بلکه کاری‌ست که انجام می‌دهم که مرا تعریف می‌کند.",
        "گاتهام به یک قهرمان نیاز ندارد، به کسی نیاز دارد که واقعیت را بپذیرد.",
    ]
    await update.message.reply_text(random.choice(quotes))


async def characters_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await db_run(_get_player, update.effective_chat.id, update.effective_user.id,
                           update.effective_user.username or "")
    await update.message.reply_text("🎭 یه شخصیت انتخاب کن:", reply_markup=build_characters_keyboard(player))


async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = await db_run(_get_chat, update.effective_chat.id)
    player = await db_run(_get_player, update.effective_chat.id, update.effective_user.id,
                           update.effective_user.username or "")
    player = collect_points(player)
    await db_run(_save_player, player)
    await send_profile(update, chat, player)


async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛒 فروشگاه گاتهام:", reply_markup=build_shop_keyboard())


async def bag_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await db_run(_get_player, update.effective_chat.id, update.effective_user.id,
                           update.effective_user.username or "")
    await update.message.reply_text(build_bag_text(player))


async def missions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    player = await db_run(_get_player, update.effective_chat.id, update.effective_user.id,
                           update.effective_user.username or "")
    player = reset_daily_mission_if_needed(player)
    await db_run(_save_player, player)

    text = (
        "📅 ماموریت روزانه:\n\n"
        f"⚔️ ۳ جنگ رو ببر ({player['wins_today']}/{DAILY_MISSION_TARGET})\n"
    )
    keyboard = None
    if player["wins_today"] >= DAILY_MISSION_TARGET and not player["mission_claimed"]:
        text += "\n✅ ماموریت تکمیل شد! جایزه‌ت رو بگیر."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🎁 دریافت جایزه", callback_data="claim_mission")]])
    elif player["mission_claimed"]:
        text += "\n🎉 جایزه امروز رو گرفتی، فردا دوباره بیا."
    await update.message.reply_text(text, reply_markup=keyboard)


async def games_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(GAMES_LIST_TEXT)


async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            text = (
                "🦇 سلام گاتهام! من ربات این گروهم.\n\n"
                "باهام بدون / و بدون منشن هم می‌تونی بازی کنی — فقط اسم بازی رو بنویس.\n"
                f"برای دیدن لیست بازی‌ها بنویس «لیست بازی» یا /games\n\n"
                f"اگه بنویسی «{KEYWORD_POINT}» پوینت می‌گیری، منشنم کن تا باهات حرف بزنم."
            )
            await update.message.reply_text(text)
        else:
            name = member.first_name or member.username or "رفیق جدید"
            text = (
                f"🦇 خوش اومدی {name} به گاتهام!\n"
                "بدون / فقط اسم یه بازی رو بنویس تا شروع بشه، یا بنویس «لیست بازی»."
            )
            await update.message.reply_text(text)



    rows = await db_run(_get_leaderboard, update.effective_chat.id, 10)
    if not rows:
        await update.message.reply_text("هنوز کسی امتیازی نگرفته!")
        return
    lines = ["🏆 رتبه‌بندی گروه:\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        name = r["username"] or "کاربر ناشناس"
        lines.append(f"{medal} @{name} — {r['score']} امتیاز")
    await update.message.reply_text("\n".join(lines))


# =========================================================
#  CALLBACK HANDLER
# =========================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    data = query.data

    if data.startswith("xo:"):
        _, xo_chat_id, index_str = data.split(":")
        xo_chat_id = int(xo_chat_id)
        index = int(index_str)
        result = handle_xo_click(xo_chat_id, user_id, index)
        if result is None:
            await query.answer("این بازی دیگه فعال نیست، دوباره بنویس «دوز».", show_alert=True)
            return
        msg, keyboard, finished = result
        if msg is None:
            await query.answer()
        else:
            await query.answer(msg, show_alert=False)
        try:
            await query.edit_message_reply_markup(reply_markup=keyboard)
        except Exception:
            pass
        return

    await query.answer()

    chat = await db_run(_get_chat, chat_id)
    player = await db_run(_get_player, chat_id, user_id, username)
    player = collect_points(player)

    if data == "show_characters":
        await query.edit_message_text("🎭 یه شخصیت انتخاب کن:", reply_markup=build_characters_keyboard(player))
        await db_run(_save_player, player)
        return

    if data == "show_profile":
        await query.edit_message_text(build_profile_text(chat, player), reply_markup=build_profile_keyboard(player))
        await db_run(_save_player, player)
        return

    if data == "show_shop":
        await query.edit_message_text("🛒 فروشگاه گاتهام:", reply_markup=build_shop_keyboard())
        await db_run(_save_player, player)
        return

    if data == "show_bag":
        await query.edit_message_text(build_bag_text(player))
        await db_run(_save_player, player)
        return

    if data.startswith("persona:"):
        persona_key = data.split(":", 1)[1]
        info = PERSONAS.get(persona_key)
        if info is None:
            return
        if player["char_level"] < info["unlock_level"]:
            await query.answer(
                f"🔒 قفله! باید سطح شخصیتت حداقل {info['unlock_level']} باشه (الان: {player['char_level']}).",
                show_alert=True,
            )
            return
        chat["persona"] = persona_key
        chat["since_switch"] = 0
        chat["next_switch_at"] = random.randint(8, 15)
        await db_run(_save_chat, chat)
        await query.edit_message_text(f"{info['label']} فعال شد. بنویس تا جواب بده!")
        await db_run(_save_player, player)
        return

    if data == "upgrade_level":
        cost = player["char_level"] * CHAR_LEVEL_COST
        if player["char_level"] >= MAX_CHAR_LEVEL:
            await query.answer("در حداکثر سطحی!", show_alert=True)
        elif player["score"] >= cost:
            player["score"] -= cost
            player["char_level"] += 1
            await db_run(_save_player, player)
            await query.edit_message_text(build_profile_text(chat, player), reply_markup=build_profile_keyboard(player))
        else:
            await query.answer(f"امتیاز کافی نداری! به {cost} امتیاز نیاز داری.", show_alert=True)
        return

    if data == "upgrade_rank":
        cost = (player["rank_index"] + 1) * RANK_COST_BASE
        if player["rank_index"] >= len(RANKS) - 1:
            await query.answer("در بالاترین مقامی!", show_alert=True)
        elif player["score"] >= cost:
            player["score"] -= cost
            player["rank_index"] += 1
            await db_run(_save_player, player)
            await query.edit_message_text(build_profile_text(chat, player), reply_markup=build_profile_keyboard(player))
        else:
            await query.answer(f"امتیاز کافی نداری! به {cost} امتیاز نیاز داری.", show_alert=True)
        return

    if data == "upgrade_pps":
        if player["points_balance"] >= PPS_UPGRADE_COST:
            player["points_balance"] -= PPS_UPGRADE_COST
            player["pps"] += PPS_UPGRADE_GAIN
            await db_run(_save_player, player)
            await query.edit_message_text(build_profile_text(chat, player), reply_markup=build_profile_keyboard(player))
        else:
            await query.answer(f"پوینت کافی نداری! به {PPS_UPGRADE_COST} پوینت نیاز داری.", show_alert=True)
        return

    if data == "upgrade_capacity":
        if player["points_balance"] >= CAPACITY_UPGRADE_COST:
            player["points_balance"] -= CAPACITY_UPGRADE_COST
            player["points_capacity"] += CAPACITY_UPGRADE_GAIN
            await db_run(_save_player, player)
            await query.edit_message_text(build_profile_text(chat, player), reply_markup=build_profile_keyboard(player))
        else:
            await query.answer(f"پوینت کافی نداری! به {CAPACITY_UPGRADE_COST} پوینت نیاز داری.", show_alert=True)
        return

    if data.startswith("buy:"):
        item_key = data.split(":", 1)[1]
        item = ITEMS.get(item_key)
        if item is None:
            return
        if player["points_balance"] >= item["price"]:
            player["points_balance"] -= item["price"]
            inv = get_inventory(player)
            inv[item_key] = inv.get(item_key, 0) + 1
            set_inventory(player, inv)
            await db_run(_save_player, player)
            await query.answer(f"{item['label']} خریداری شد!", show_alert=True)
        else:
            await query.answer(f"پوینت کافی نداری! به {item['price']} پوینت نیاز داری.", show_alert=True)
        return

    if data == "claim_mission":
        player = reset_daily_mission_if_needed(player)
        if player["wins_today"] >= DAILY_MISSION_TARGET and not player["mission_claimed"]:
            player["mission_claimed"] = 1
            player["score"] += DAILY_MISSION_REWARD_SCORE
            player["points_balance"] = min(
                player["points_capacity"], player["points_balance"] + DAILY_MISSION_REWARD_POINTS
            )
            await db_run(_save_player, player)
            await query.edit_message_text(
                f"🎁 جایزه گرفتی: +{DAILY_MISSION_REWARD_SCORE} امتیاز و +{DAILY_MISSION_REWARD_POINTS} پوینت!"
            )
        else:
            await query.answer("هنوز ماموریت تکمیل نشده یا قبلاً گرفتیش.", show_alert=True)
        return

    await db_run(_save_player, player)


# =========================================================
#  BATTLE LOGIC
# =========================================================

async def maybe_start_battle(update: Update, chat) -> bool:
    chat["since_battle"] += 1
    if chat["battle_enemy"] == "" and chat["since_battle"] >= chat["next_battle_at"]:
        enemy = random.choice(ENEMIES)
        chat["battle_enemy"] = enemy["name"]
        chat["battle_attempts"] = 0
        chat["battle_max_attempts"] = 3
        chat["since_battle"] = 0
        chat["next_battle_at"] = random.randint(10, 20)
        await update.message.reply_text(
            f"🚨 جنگ شد! گاتهام تو خطره!\n{enemy['clue']}\n"
            f"زود حدس بزن این دشمن کیه (فقط اسمشو بنویس)!"
        )
        return True
    return False


async def handle_battle_guess(update: Update, chat, player, text: str) -> bool:
    if not chat["battle_enemy"]:
        return False

    enemy = next((e for e in ENEMIES if e["name"] == chat["battle_enemy"]), None)
    if enemy is None:
        chat["battle_enemy"] = ""
        return False

    guess = text.strip().lower()
    if guess in [a.lower() for a in enemy["aliases"]]:
        inv = get_inventory(player)
        multiplier = 1
        if inv.get("batarang", 0) > 0:
            inv["batarang"] -= 1
            set_inventory(player, inv)
            multiplier = 2
        reward = 10 * player["char_level"] * multiplier
        player["score"] += reward
        player = reset_daily_mission_if_needed(player)
        player["wins_today"] += 1

        chat["battle_enemy"] = ""
        chat["battle_attempts"] = 0

        extra = " (باتارنگ استفاده شد ⚡️۲x)" if multiplier == 2 else ""
        msg = f"✅ درسته! {enemy['name']} رو شکست دادی و گاتهام رو نجات دادی!\n+{reward} امتیاز 🏆{extra}"
        if player["wins_today"] == DAILY_MISSION_TARGET and not player["mission_claimed"]:
            msg += "\n\n📅 ماموریت روزانه تکمیل شد! با /missions جایزه‌تو بگیر."
        await update.message.reply_text(msg)
    else:
        chat["battle_attempts"] += 1
        inv = get_inventory(player)
        if chat["battle_attempts"] >= chat["battle_max_attempts"] and inv.get("antidote", 0) > 0:
            inv["antidote"] -= 1
            set_inventory(player, inv)
            chat["battle_max_attempts"] += 1
            await update.message.reply_text("🧪 پادزهر مصرف شد! یه فرصت اضافه گرفتی.")
        if chat["battle_attempts"] >= chat["battle_max_attempts"]:
            enemy_name = enemy["name"]
            chat["battle_enemy"] = ""
            chat["battle_attempts"] = 0
            await update.message.reply_text(
                f"❌ وقتت تموم شد! دشمن {enemy_name} بود. گاتهام یه ضربه خورد، ولی بازم می‌جنگیم!"
            )
        else:
            await update.message.reply_text("❌ غلطه، دوباره حدس بزن!")
    return True


# =========================================================
#  MAIN MESSAGE HANDLER
# =========================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    username = update.effective_user.username or ""
    text = update.message.text
    is_group = update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)

    if not check_rate_limit(user_id):
        return  # ضد اسپم: سکوت کامل تا پنجره زمانی تموم بشه

    player = await db_run(_get_player, chat_id, user_id, username)
    player = collect_points(player)

    # --- کلیدواژه "بتمن" برای گرفتن پوینت، حتی بدون منشن، تو گروه‌ها ---
    if KEYWORD_POINT in text:
        now = time.time()
        if now - player.get("last_keyword_ts", 0) >= KEYWORD_COOLDOWN:
            player["last_keyword_ts"] = now
            player["points_balance"] = min(
                player["points_capacity"], player["points_balance"] + KEYWORD_REWARD
            )

    # --- بازی‌ها: بدون نیاز به منشن و بدون / ، فقط با نوشتن اسم بازی یا حدس ---
    handled, reply, keyboard = try_start_game(chat_id, user_id, text)
    if handled:
        await update.message.reply_text(reply, reply_markup=keyboard)
        await db_run(_save_player, player)
        return

    handled, reply = handle_game_guess(chat_id, user_id, text)
    if handled:
        if reply:
            await update.message.reply_text(reply)
        await db_run(_save_player, player)
        return

    mentioned = is_bot_mentioned(update, context)
    if is_group and not mentioned:
        await db_run(_save_player, player)
        return  # تو گروه فقط با منشن ادامه بده

    chat = await db_run(_get_chat, chat_id)

    if chat["battle_enemy"]:
        consumed = await handle_battle_guess(update, chat, player, text)
        if consumed:
            await db_run(_save_chat, chat)
            await db_run(_save_player, player)
            return

    started = await maybe_start_battle(update, chat)
    if started:
        await db_run(_save_chat, chat)
        await db_run(_save_player, player)
        return

    chat["since_switch"] += 1
    if chat["since_switch"] >= chat["next_switch_at"]:
        new_persona = random.choice([p for p in PERSONAS if p != chat["persona"]])
        chat["persona"] = new_persona
        chat["since_switch"] = 0
        chat["next_switch_at"] = random.randint(8, 15)
        await update.message.reply_text(f"🔄 شخصیت عوض شد: {PERSONAS[new_persona]['label']}")

    reply = await call_ai(chat_id, chat["persona"], player["char_level"], text)
    await update.message.reply_text(reply)

    await db_run(_save_chat, chat)
    await db_run(_save_player, player)


# =========================================================
#  MAIN
# =========================================================

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN تنظیم نشده! برو تو Railway Variables اضافه‌اش کن.")

    _init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("characters", characters_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("bag", bag_cmd))
    app.add_handler(CommandHandler("missions", missions_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("games", games_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("🦇 Batman Gotham Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
