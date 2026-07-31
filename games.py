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

import random
from collections import defaultdict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

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
}

GAMES_LIST_TEXT = (
    "🎮 لیست بازی‌ها (مرحله اول - فقط اسمشو بنویس، بدون /):\n\n"
    "✊ سنگ کاغذ قیچی\n"
    "❌ دوز\n"
    "🔢 حدس عدد\n"
    "🏙️ حدس شهر\n"
    "🌍 حدس کشور\n"
    "🎨 حدس رنگ\n"
    "🎬 حدس فیلم\n"
    "🔤 هنگمن\n"
    "🎯 جرأت یا حقیقت\n"
    "🤔 چی ترجیح میدی\n"
    "📜 ضرب المثل\n"
    "📖 فال حافظ\n"
    "🔮 طالع بینی\n"
    "😂 جوک\n"
    "🎲 تاس\n\n"
    "بقیه‌ی بازی‌ها (تا ۶۰ تا) تو مراحل بعدی اضافه می‌شن."
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

    if key in ("guess_city", "guess_country", "guess_color", "guess_movie"):
        answer = sess["data"]["answer"]
        if guess in [a.lower() for a in answer["aliases"]]:
            clear_session(chat_id)
            return True, f"✅ درسته! جواب «{answer['name']}» بود. {taunt_win()}"
        return True, f"❌ غلطه. {taunt_lose()} دوباره امتحان کن."

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
