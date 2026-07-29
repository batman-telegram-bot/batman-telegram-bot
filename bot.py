import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🦇 من بتمنم! گاردین گاتهام سیتی.\n"
        "دستورات:\n"
        "/start - شروع\n"
        "/quote - یه جمله بتمنی\n"
    )


async def quote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quotes = [
        "من از تاریکی نمی‌ترسم، من خودِ تاریکی‌ام.",
        "این چیزی نیست که من هستم، بلکه کاری‌ست که انجام می‌دهم که مرا تعریف می‌کند.",
        "گاتهام به یک قهرمان نیاز ندارد، به کسی نیاز دارد که واقعیت را بپذیرد.",
    ]
    import random
    await update.message.reply_text(random.choice(quotes))


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🦇 {update.message.text}")


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN تنظیم نشده! برو تو Railway Variables اضافه‌اش کن.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quote", quote))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    print("🦇 Batman Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
