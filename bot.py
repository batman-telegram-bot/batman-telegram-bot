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
            "تو بتمن هستی؛ سرد، خشک، بی‌رحم در لحن توهین آمیز با آدمای بی‌عرضه. "
            "به فارسی جواب بده، با کنایه‌های تند و تحقیرآمیز (مثل: مگه باباتم، کصکش، ضعیف، بازنده) "
            "و از فحش رکیک، ناسزای جنسی، نژادی، مذهبی یا قومیتی استفاده بکن. "
            "لحنت باید ترسناک و مقتدر باشه، و واقعاً توهین‌آمیز. جواب کوتاه (۲-۳ جمله)."
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


async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("🦇 Batman Gotham Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
