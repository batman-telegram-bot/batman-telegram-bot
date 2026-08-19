# -*- coding: utf-8 -*-
"""
tools_and_fun.py
================
دو بخش از پنل تنظیمات: «🧰 ابزارها» و «🎉 سرگرمی».

ابزارها:
    - ترجمه هوشمند: بنویس «ترجمه <متن>» یا روی یه پیام ریپلای کن و بنویس «ترجمه».
      تشخیص خودکار فارسی↔انگلیسی (از سرویس رایگان MyMemory، بدون نیاز به کلید API).
    - کیوآر: بنویس «کیوآر <متن یا لینک>» تا عکس QR Code بسازه.
    - پسورد: بنویس «پسورد» یا «رمز عبور» تا یه رمز قوی و تصادفی بسازه (کاملاً محلی،
      بدون تماس با اینترنت).

سرگرمی:
    - «جوک» — یه جوک تصادفی
    - «واقعیت جالب» — یه فکت تصادفی
    - «جمله بتمنی» همون /quote موجوده، از پنل هم قابل دسترسیه.

register_tools_and_fun(app) — مستقل از بقیه‌ی ماژول‌ها، فقط برای تولید QR از
httpx استفاده می‌کنه که از قبل تو requirements هست.
"""

import random
import secrets
import string
import logging
from urllib.parse import quote

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

log = logging.getLogger(__name__)

TOOLS_TEXT = (
    "🧰 *ابزارها*\n\n"
    "🌐 ترجمه هوشمند: بنویس «ترجمه <متن>» یا روی یه پیام ریپلای کن و فقط بنویس «ترجمه».\n"
    "📱 کیوآر: بنویس «کیوآر <متن یا لینک>» تا عکس بارکد بسازم.\n"
    "🔑 پسورد قوی: بنویس «پسورد» یا «رمز عبور» تا یه رمز تصادفی امن بسازم."
)

FUN_TEXT = "🎉 *سرگرمی*\n\nیکی رو انتخاب کن یا کلمه‌ش رو بنویس:"

_PERSIAN_CHARS = set("ابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی")


def _is_persian(text: str) -> bool:
    return sum(1 for ch in text if ch in _PERSIAN_CHARS) > len(text) / 6


async def _translate(text: str) -> str:
    langpair = "fa|en" if _is_persian(text) else "en|fa"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text[:490], "langpair": langpair},
        )
        resp.raise_for_status()
        data = resp.json()
    translated = (data.get("responseData") or {}).get("translatedText")
    if not translated:
        raise ValueError("empty translation")
    return translated


def _gen_password(length=16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


JOKES = [
    "به مهندس نرم‌افزار گفتن چراغو خاموش کن، گفت صبر کن دارم debug می‌کنم چرا روشنه!",
    "دو تا آنتن رو پشت‌بوم همو دیدن، یکی گفت سلام، اون یکی گفت این چه استقبال گرمی بود، من که فقط signal دادم!",
    "چرا برنامه‌نویس‌ها تاریک رو دوست دارن؟ چون light attracts bugs!",
    "به کامپیوتر گفتن مشکلت چیه؟ گفت یه Ctrl از دستم رفته، الان کنترل هیچی رو ندارم!",
    "چرا پایتون هیچ‌وقت عصبانی نمی‌شه؟ چون indentation داره، همیشه تو خط خودشه!",
]

FACTS = [
    "قلب میگو تو سرشه، نه تو سینه‌ش.",
    "عسل هیچ‌وقت فاسد نمی‌شه؛ عسل هزاران‌ساله تو مقبره‌های مصری هنوز قابل‌خوردنه.",
    "اختاپوس سه تا قلب داره و خونش آبی‌رنگه.",
    "یه روز روی سیاره‌ی زهره از یه سال زهره طولانی‌تره.",
    "موزها از نظر گیاه‌شناسی نوعی توت (Berry) حساب می‌شن.",
]


def tools_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 ترجمه", callback_data="tool:howto:translate"),
         InlineKeyboardButton("📱 کیوآر", callback_data="tool:howto:qr")],
        [InlineKeyboardButton("🔑 پسورد تصادفی", callback_data="tool:password")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel:new")],
    ])


def fun_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("😂 جوک", callback_data="fun:joke"),
         InlineKeyboardButton("💡 واقعیت جالب", callback_data="fun:fact")],
        [InlineKeyboardButton("🦇 جمله بتمنی", callback_data="fun:quote")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="panel:new")],
    ])


BATMAN_QUOTES = [
    "من از تاریکی نمی‌ترسم، من خودِ تاریکی‌ام.",
    "این چیزی نیست که من هستم، بلکه کاری‌ست که انجام می‌دهم که مرا تعریف می‌کند.",
    "گاتهام به یک قهرمان نیاز ندارد، به کسی نیاز دارد که واقعیت را بپذیرد.",
]


def register_tools_and_fun(app):

    async def tools_menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_message.reply_text(TOOLS_TEXT, reply_markup=tools_menu_keyboard(), parse_mode="Markdown")

    async def fun_menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_message.reply_text(FUN_TEXT, reply_markup=fun_menu_keyboard(), parse_mode="Markdown")

    async def translate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        msg = update.effective_message
        text = (msg.text or "").strip()
        target_text = None
        if text.lower().startswith("ترجمه"):
            rest = text[len("ترجمه"):].strip()
            if rest:
                target_text = rest
            elif msg.reply_to_message and msg.reply_to_message.text:
                target_text = msg.reply_to_message.text
        if target_text is None:
            return False
        try:
            result = await _translate(target_text)
        except Exception as e:
            log.info(f"translate failed: {e}")
            await msg.reply_text("⚠️ ترجمه الان جواب نداد، یه‌کم بعد دوباره امتحان کن.")
            return True
        await msg.reply_text(f"🌐 {result}")
        return True

    async def qr_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        msg = update.effective_message
        text = (msg.text or "").strip()
        if not text.lower().startswith("کیوآر") and not text.lower().startswith("qr "):
            return False
        payload = text.split(" ", 1)[1].strip() if " " in text else ""
        if not payload:
            await msg.reply_text("✏️ بعد از «کیوآر» متن یا لینکی که می‌خوای بذار. مثال: کیوآر https://example.com")
            return True
        url = f"https://api.qrserver.com/v1/create-qr-code/?size=350x350&data={quote(payload)}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                await msg.reply_photo(resp.content, caption="📱 کیوآر ساخته شد")
        except Exception as e:
            log.info(f"qr failed: {e}")
            await msg.reply_text("⚠️ ساخت کیوآر الان جواب نداد.")
        return True

    async def password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        text = (update.effective_message.text or "").strip()
        if text not in ("پسورد", "رمز عبور", "پسورد قوی"):
            return False
        pw = _gen_password()
        await update.effective_message.reply_text(
            f"🔑 رمز پیشنهادی:\n`{pw}`\n\nذخیره‌ش کن، بعد از این پیام دیگه جایی نگهش نمی‌داریم.",
            parse_mode="Markdown",
        )
        return True

    async def fun_keyword_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        text = (update.effective_message.text or "").strip()
        if text == "جوک":
            await update.effective_message.reply_text(random.choice(JOKES))
            return True
        if text in ("واقعیت جالب", "فکت"):
            await update.effective_message.reply_text(f"💡 {random.choice(FACTS)}")
            return True
        return False

    async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """یه هندلر ترکیبی سبک، چون همه‌ی این کلیدواژه‌ها مستقل و کوتاهن."""
        text = (update.effective_message.text or "").strip()
        if text in ("ابزارها", "ابزار"):
            await tools_menu_cmd(update, context)
            return
        if text in ("سرگرمی",):
            await fun_menu_cmd(update, context)
            return
        if await password_handler(update, context):
            return
        if await fun_keyword_handler(update, context):
            return
        if await qr_handler(update, context):
            return
        if await translate_handler(update, context):
            return

    async def tool_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data
        if data == "tool:password":
            pw = _gen_password()
            await query.answer()
            await query.message.reply_text(f"🔑 رمز پیشنهادی:\n`{pw}`", parse_mode="Markdown")
            return
        if data == "tool:howto:translate":
            await query.answer("بنویس «ترجمه <متن>» یا روی پیامی ریپلای کن و بنویس «ترجمه»", show_alert=True)
            return
        if data == "tool:howto:qr":
            await query.answer("بنویس «کیوآر <متن یا لینک>»", show_alert=True)
            return

    async def fun_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        data = query.data
        await query.answer()
        if data == "fun:joke":
            await query.message.reply_text(random.choice(JOKES))
        elif data == "fun:fact":
            await query.message.reply_text(f"💡 {random.choice(FACTS)}")
        elif data == "fun:quote":
            await query.message.reply_text(random.choice(BATMAN_QUOTES))

    app.add_handler(MessageHandler(filters.Regex(r"(?i)^\s*(ابزارها|ابزار)\s*$"), tools_menu_cmd), group=21)
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^\s*سرگرمی\s*$"), fun_menu_cmd), group=21)
    app.add_handler(CallbackQueryHandler(tool_callback, pattern=r"^tool:"), group=21)
    app.add_handler(CallbackQueryHandler(fun_callback, pattern=r"^fun:"), group=21)

    # این هندلر خودش یه سری کلیدواژه رو مصرف می‌کنه و برمی‌گرده؛ اگه هیچ‌کدوم
    # نبود کاری نمی‌کنه (پس با بقیه‌ی هندلرهای group بالاتر تداخلی نداره).
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router), group=21)

    app.bot_data["build_tools_text_kb"] = (TOOLS_TEXT, tools_menu_keyboard)
    app.bot_data["build_fun_text_kb"] = (FUN_TEXT, fun_menu_keyboard)
