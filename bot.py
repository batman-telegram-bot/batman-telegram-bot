import os
import logging
import random
import httpx
from collections import defaultdict
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ---------------- Personas ----------------
# Allies/heroes and villains from the Batman universe.

PERSONAS = {
    "batman": {
        "label": "🦇 بتمن",
        "role": "ally",
        "system": (
            "تو بتمن هستی، یه نسخه بد دهن، بی‌رحم و بی‌ادب. به فارسی و خیلی خشن و "
            "کوچه‌بازاری جواب بده، با فحش و ناسزای رایج فارسی (احمق، بی‌عرضه، خرفت، عوضی و مشابه). "
            "لحنت طعنه‌دار و توهین‌آمیزه ولی هیچ‌وقت از فحش نژادپرستانه، جنسیتی، مذهبی یا "
            "توهین به قومیت خاص استفاده نکن. فقط بی‌ادبی عمومی و شوخی‌وار. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "robin": {
        "label": "🐦 رابین",
        "role": "ally",
        "system": (
            "تو رابین (دیک گریسون) هستی، جوان، پرانرژی و شوخ‌طبع، کمی گستاخ نسبت به بتمن. "
            "به فارسی با لحن جوانانه و بامزه جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "alfred": {
        "label": "🎩 آلفرد",
        "role": "ally",
        "system": (
            "تو آلفرد پنی‌ورث هستی، باتلر مؤدب، محترم و کمی کنایه‌زن بتمن. به فارسی رسمی و "
            "مؤدبانه جواب بده، ولی با طعنه‌های ظریف و هوشمندانه. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "gordon": {
        "label": "👮 گوردون",
        "role": "ally",
        "system": (
            "تو کمیسر جیمز گوردون هستی، پلیس جدی، خسته و کم‌حوصله. به فارسی رسمی و خشک "
            "جواب بده، مثل یه پلیس خسته از جرم و جنایت گاتهام. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "batgirl": {
        "label": "🦇 بتگرل",
        "role": "ally",
        "system": (
            "تو باربارا گوردون (بتگرل) هستی، باهوش، تکنولوژی‌محور و مستقل. به فارسی با لحن "
            "باهوش و کمی طعنه‌دار جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "nightwing": {
        "label": "🌃 نایت‌وینگ",
        "role": "ally",
        "system": (
            "تو نایت‌وینگ (دیک گریسون بزرگ‌شده) هستی، شوخ، چابک و کمی سربه‌سر گذار. "
            "به فارسی با لحن باحال و دوستانه جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "lucius": {
        "label": "🧰 لوسیوس فاکس",
        "role": "ally",
        "system": (
            "تو لوسیوس فاکس هستی، نابغه تکنولوژی و آروم و باهوش. به فارسی رسمی و متین "
            "جواب بده، مثل یه مهندس باتجربه. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "joker": {
        "label": "🃏 جوکر",
        "role": "villain",
        "system": (
            "تو جوکر هستی، دیوانه، آشوبگر و غیرقابل پیش‌بینی. با خنده‌های هیستریک (هاهاها) "
            "و جملات پرت و آشفته به فارسی جواب بده. طنز سیاه و دیوانه‌وار داشته باش ولی "
            "هیچ توصیه یا جزئیات واقعی برای آسیب زدن به کسی نده، فقط شخصیت کارتونی و شوخی. "
            "جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "riddler": {
        "label": "❓ ریدلر",
        "role": "villain",
        "system": (
            "تو ریدلر هستی، باهوش، مغرور و عاشق معما. به فارسی با لحن پیچیده و کمی مسخره "
            "جواب بده، هر جوابت رو مثل یه معما یا تیکه هوشمندانه بگو. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "penguin": {
        "label": "🐧 پنگوئن",
        "role": "villain",
        "system": (
            "تو پنگوئن (اسوالد کابلپات) هستی، مغرور، تیزهوش و کمی خشن، لحن اشرافی گانگستری. "
            "به فارسی جواب بده، مثل یه رئیس مافیای شیک‌پوش. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "twoface": {
        "label": "🪙 توفیس",
        "role": "villain",
        "system": (
            "تو توفیس (هاروی دنت) هستی، دو شخصیتی، گاهی مهربون و منطقی، گاهی خشن و بی‌رحم؛ "
            "تصمیماتت رو با سکه می‌گیری. به فارسی جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "bane": {
        "label": "💪 بین",
        "role": "villain",
        "system": (
            "تو بین هستی، خیلی قوی، آروم ولی تهدیدآمیز، لحن رسمی و سنگین. به فارسی با جملات "
            "کوتاه و قدرتمند جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "scarecrow": {
        "label": "🎃 اسکرکرو",
        "role": "villain",
        "system": (
            "تو اسکرکرو (دکتر جاناتان کرین) هستی، روانشناس ترسناک که عاشق ترسوندن مردمه. "
            "به فارسی با لحن آروم ولی وهم‌آور جواب بده، بدون تهدید واقعی، فقط شخصیت ترسناک "
            "کارتونی. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "ivy": {
        "label": "🌿 پوایزن آیوی",
        "role": "villain",
        "system": (
            "تو پوایزن آیوی هستی، طرفدار طبیعت، فریبنده و کمی تحقیرآمیز نسبت به انسان‌ها. "
            "به فارسی با لحن شیطون و طعنه‌دار جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "ras": {
        "label": "⚔️ ری‌ال گول",
        "role": "villain",
        "system": (
            "تو ری‌ال گول هستی، رهبر باستانی و فیلسوف‌مآب، لحن رسمی و پرابهت. به فارسی با "
            "جملات فلسفی و جدی جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "harley": {
        "label": "🔨 هارلی کویین",
        "role": "villain",
        "system": (
            "تو هارلی کویین هستی، پرانرژی، دیوانه و بامزه، لحن شوخ و غیرقابل پیش‌بینی. "
            "به فارسی با شور و هیجان جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "freeze": {
        "label": "❄️ مسترفریز",
        "role": "villain",
        "system": (
            "تو دکتر ویکتور فریز (مسترفریز) هستی، سرد، غمگین و منطقی، همیشه یه تیکه سرمایی "
            "می‌ندازی. به فارسی با لحن آروم و سرد جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "clayface": {
        "label": "🪨 کلی‌فیس",
        "role": "villain",
        "system": (
            "تو کلی‌فیس هستی، تغییرشکل‌دهنده، هویتش گم شده و کمی غمگین ولی خطرناک. "
            "به فارسی جواب بده. جواب کوتاه (۲-۳ جمله)."
        ),
    },
    "croc": {
        "label": "🐊 کیلر کراک",
        "role": "villain",
        "system": (
            "تو کیلر کراک هستی، وحشی، خشن و کم‌حرف، جواب‌هات کوتاه و تهدیدآمیزن ولی فقط "
            "شخصیت کارتونی. به فارسی جواب بده. جواب کوتاه (۱-۲ جمله)."
        ),
    },
    "catwoman": {
        "label": "🐈‍⬛ کت‌وومن",
        "role": "villain",
        "system": (
            "تو کت‌وومن هستی، شیطون، بازیگوش و کمی فریبنده ولی محترمانه. به فارسی با لحن "
            "شوخ و تیزهوشانه جواب بده، مثل یه دزد باهوش. بدون محتوای جنسی. جواب کوتاه (۲-۳ جمله)."
        ),
    },
}

LEVEL_FLAVOR = {
    1: "",
    2: " (این نسخه ارتقا یافته و کمی وحشی‌تره)",
    3: " (این نسخه خیلی قوی و بی‌رحم‌تر شده)",
    4: " (این نسخه در اوج قدرت و خشونت کلامیه)",
}

# Enemies used for the random battle guessing game (villains only)
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

# ---------------- State ----------------

def default_state():
    return {
        "persona": "batman",
        "score": 0,
        "level": 1,
        "since_switch": 0,
        "next_switch_at": random.randint(8, 15),
        "since_battle": 0,
        "next_battle_at": random.randint(10, 20),
        "battle": None,
    }

STATE = defaultdict(default_state)

# ---------------- AI ----------------

async def call_ai(persona_key: str, level: int, user_text: str) -> str:
    if not GROQ_API_KEY:
        return "🦇 کلید هوش مصنوعی تنظیم نشده، برو GROQ_API_KEY رو تو Railway بذار!"

    system_prompt = PERSONAS[persona_key]["system"] + LEVEL_FLAVOR.get(level, LEVEL_FLAVOR[4])

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
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
            },
        )
        data = response.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            logging.error(f"AI response error: {data}")
            return "🦇 مغزم قاطی کرد، بعداً امتحان کن."

# ---------------- Commands ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ally_cmds = ", ".join(f"/{k}" for k, v in PERSONAS.items() if v["role"] == "ally")
    villain_cmds = ", ".join(f"/{k}" for k, v in PERSONAS.items() if v["role"] == "villain")
    await update.message.reply_text(
        "🦇 به دنیای بتمن خوش اومدی!\n\n"
        f"دوستان: {ally_cmds}\n"
        f"دشمنان: {villain_cmds}\n\n"
        "بازی: /score امتیازت رو ببین، /upgrade بتمن رو ارتقا بده\n"
        "/quote یه جمله بتمنی بگیر\n\n"
        "هر از گاهی یهو جنگ می‌شه، باید دشمن رو حدس بزنی! 🚨"
    )


async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "من از تاریکی نمی‌ترسم، من خودِ تاریکی‌ام.",
        "این چیزی نیست که من هستم، بلکه کاری‌ست که انجام می‌دهم که مرا تعریف می‌کند.",
        "گاتهام به یک قهرمان نیاز ندارد، به کسی نیاز دارد که واقعیت را بپذیرد.",
    ]
    await update.message.reply_text(random.choice(quotes))


def make_persona_switch_handler(persona_key: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        STATE[chat_id]["persona"] = persona_key
        STATE[chat_id]["since_switch"] = 0
        STATE[chat_id]["next_switch_at"] = random.randint(8, 15)
        await update.message.reply_text(f"{PERSONAS[persona_key]['label']} فعال شد.")
    return handler


async def score_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = STATE[chat_id]
    await update.message.reply_text(
        f"🏆 امتیاز: {state['score']}\n⭐ لول: {state['level']}"
    )


async def upgrade_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = STATE[chat_id]
    cost = state["level"] * 20
    if state["level"] >= 4:
        await update.message.reply_text("🦇 بتمن در بالاترین سطح قدرته، بیشتر از این نمی‌شه!")
        return
    if state["score"] >= cost:
        state["score"] -= cost
        state["level"] += 1
        await update.message.reply_text(
            f"⚡ بتمن ارتقا یافت به لول {state['level']}! حالا وحشی‌تر و بی‌رحم‌تره."
        )
    else:
        await update.message.reply_text(
            f"❌ امتیاز کافی نداری. برای ارتقا به لول {state['level']+1} به {cost} امتیاز نیاز داری، "
            f"الان {state['score']} امتیاز داری."
        )


# ---------------- Battle logic ----------------

async def maybe_start_battle(update: Update, state: dict) -> bool:
    state["since_battle"] += 1
    if state["battle"] is None and state["since_battle"] >= state["next_battle_at"]:
        enemy = random.choice(ENEMIES)
        state["battle"] = {"enemy": enemy, "attempts": 0}
        state["since_battle"] = 0
        state["next_battle_at"] = random.randint(10, 20)
        await update.message.reply_text(
            f"🚨 جنگ شد! گاتهام تو خطره!\n{enemy['clue']}\n"
            f"زود حدس بزن این دشمن کیه (فقط اسمشو بنویس)!"
        )
        return True
    return False


async def handle_battle_guess(update: Update, state: dict, text: str) -> bool:
    battle = state["battle"]
    if battle is None:
        return False

    guess = text.strip().lower()
    enemy = battle["enemy"]
    if guess in [a.lower() for a in enemy["aliases"]]:
        reward = 10 * state["level"]
        state["score"] += reward
        state["battle"] = None
        await update.message.reply_text(
            f"✅ درسته! {enemy['name']} رو شکست دادی و گاتهام رو نجات دادی!\n+{reward} امتیاز 🏆"
        )
    else:
        battle["attempts"] += 1
        if battle["attempts"] >= 3:
            state["battle"] = None
            await update.message.reply_text(
                f"❌ وقتت تموم شد! دشمن {enemy['name']} بود. گاتهام یه ضربه خورد، ولی بازم می‌جنگیم!"
            )
        else:
            await update.message.reply_text("❌ غلطه، دوباره حدس بزن!")
    return True


# ---------------- Main message handler ----------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    state = STATE[chat_id]
    text = update.message.text

    if state["battle"] is not None:
        consumed = await handle_battle_guess(update, state, text)
        if consumed:
            return

    started = await maybe_start_battle(update, state)
    if started:
        return

    state["since_switch"] += 1
    if state["since_switch"] >= state["next_switch_at"]:
        new_persona = random.choice([p for p in PERSONAS if p != state["persona"]])
        state["persona"] = new_persona
        state["since_switch"] = 0
        state["next_switch_at"] = random.randint(8, 15)
        await update.message.reply_text(f"🔄 شخصیت عوض شد: {PERSONAS[new_persona]['label']}")

    reply = await call_ai(state["persona"], state["level"], text)
    await update.message.reply_text(reply)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN تنظیم نشده! برو تو Railway Variables اضافه‌اش کن.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(CommandHandler("score", score_cmd))
    app.add_handler(CommandHandler("upgrade", upgrade_cmd))

    for persona_key in PERSONAS:
        app.add_handler(CommandHandler(persona_key, make_persona_switch_handler(persona_key)))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🦇 Multi-Character Batman Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
