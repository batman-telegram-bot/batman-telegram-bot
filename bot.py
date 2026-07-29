import os
import logging
import random
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

SYSTEM_PROMPT = (
    "تو بتمن هستی، ولی یه نسخه بد دهن، بی‌رحم و بی‌ادب از بتمن. "
    "به فارسی و خیلی خشن و کوچه‌بازاری جواب بده، با فحش و ناسزای رایج فارسی "
    "(مثل احمق، بی‌عرضه، خرفت، عوضی و مشابه). لحنت باید طعنه‌دار و توهین‌آمیز باشه "
    "ولی هیچ‌وقت از فحش‌های نژادپرستانه، جنسیتی، مذهبی یا توهین به یک قومیت/گروه خاص "
    "استفاده نکن. فقط بی‌ادبی و ناسزای عمومی و شوخی‌وار، در قالب شخصیت بتمن عصبانی. "
    "جواب‌ها کوتاه باشن (حداکثر ۲-۳ جمله)."
)


async def call_ai(user_text: str) -> str:
    if not ANTHROPIC_API_KEY:
        return "🦇 کلید هوش مصنوعی تنظیم نشده، برو ANTHROPIC_API_KEY رو تو Railway بذار احمق!"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-5",
                "max_tokens": 300,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_text}],
            },
        )
        data = response.json()
        try:
            return data["content"][0]["text"]
        except (KeyError, IndexError):
            logging.error(f"AI response error: {data}")
            return "🦇 مغزم قاطی کرد، بعداً امتحان کن."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🦇 من بتمنم! ولی نسخه عصبانی و بد دهنش. هرچی بگی جوابتو با فحش می‌دم.\n"
        "/quote - یه جمله بتمنی\n"
    )


async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "من از تاریکی نمی‌ترسم، من خودِ تاریکی‌ام، حالا گمشو کنار.",
        "این چیزی نیست که من هستم، بلکه کاری‌ست که انجام می‌دهم، برخلاف تو که هیچ غلطی نمی‌کنی.",
        "گاتهام به یک قهرمان نیاز ندارد، به آدمی نیاز داره که مثل تو ابله نباشه.",
    ]
    await update.message.reply_text(random.choice(quotes))


async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply = await call_ai(update.message.text)
    await update.message.reply_text(reply)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN تنظیم نشده! برو تو Railway Variables اضافه‌اش کن.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_reply))

    print("🦇 Angry Batman AI Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
