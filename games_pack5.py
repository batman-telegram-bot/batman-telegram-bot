# games_pack5.py
# 🦇 Gotham Games Pack 5
# بازی‌های: منچ، مار و پله، شطرنج
#
# نصب:
#   در bot.py / bot-gotham-fixed.py:
#       from games_pack5 import register_games_pack5
#   و داخل main():
#       register_games_pack5(app)
#
# نکته:
# بازی‌ها حافظه‌ای هستند و با ری‌استارت ربات بازی‌های در حال اجرا پاک می‌شوند.

import random
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler


# =========================================================
# عمومی
# =========================================================

LADDERS = {
    3: 22, 5: 8, 11: 26, 20: 29, 27: 56,
    36: 44, 51: 67, 71: 92, 80: 99,
}
SNAKES = {
    17: 4, 19: 7, 21: 9, 43: 34, 48: 30,
    62: 18, 64: 60, 87: 24, 93: 73, 95: 75, 98: 79,
}

# game_id -> state
MANCH = {}
SNAKE = {}


def _name(user):
    return user.first_name or user.username or str(user.id)


def _mention(user):
    return f'<a href="tg://user?id={user.id}">{_name(user)}</a>'


def _board_100(pos):
    cells = []
    for row in range(9, -1, -1):
        nums = list(range(row * 10 + 1, row * 10 + 11))
        if row % 2 == 1:
            nums.reverse()
        cells.append(" ".join(f"{n:02}" for n in nums))
    return "\n".join(cells)


# =========================================================
# 🎲 منچ
# =========================================================

def _manch_kb(game):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 تاس", callback_data=f"g5:m:d:{game['id']}"),
            InlineKeyboardButton("🚪 خروج", callback_data=f"g5:m:x:{game['id']}"),
        ]
    ])


def _manch_text(game):
    lines = [
        "🎲 <b>منچ گاتهام</b>",
        "",
        f"👑 نوبت: {_mention(game['players'][game['turn']])}",
        f"🎯 بازیکنان: {len(game['players'])}/4",
        "",
    ]
    for i, u in enumerate(game["players"]):
        lines.append(f"{i+1}. {_mention(u)} — خانه {game['pos'][u.id]}")
    lines += ["", "برای بازی تاس را بزن 🎲"]
    return "\n".join(lines)


async def manch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    gid = update.effective_chat.id
    if gid in MANCH:
        await update.message.reply_text("🎲 یک بازی منچ همین الان در جریانه.")
        return
    MANCH[gid] = {
        "id": str(gid),
        "players": [update.effective_user],
        "pos": {update.effective_user.id: 0},
        "turn": 0,
        "started": False,
    }
    await update.message.reply_text(
        f"🎲 <b>منچ گاتهام ساخته شد!</b>\n"
        f"👤 سازنده: {_mention(update.effective_user)}\n"
        f"حداکثر ۴ بازیکن.\n\n"
        f"بازیکن‌های بعدی بنویسن <b>/joinmanch</b>\n"
        f"وقتی آماده بودید <b>/startmanch</b>",
        parse_mode="HTML",
    )


async def join_manch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    game = MANCH.get(gid)
    if not game:
        await update.message.reply_text("🎲 اول /manch رو بزن.")
        return
    if game["started"]:
        await update.message.reply_text("🎲 بازی شروع شده؛ دیر رسیدی!")
        return
    uid = update.effective_user.id
    if any(u.id == uid for u in game["players"]):
        await update.message.reply_text("تو از قبل داخل بازی هستی 😄")
        return
    if len(game["players"]) >= 4:
        await update.message.reply_text("🎲 ظرفیت منچ پر شده.")
        return
    game["players"].append(update.effective_user)
    game["pos"][uid] = 0
    await update.message.reply_text(
        f"✅ {_mention(update.effective_user)} وارد منچ شد!\n"
        f"بازیکنان: {len(game['players'])}/4",
        parse_mode="HTML",
    )


async def start_manch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    game = MANCH.get(gid)
    if not game:
        await update.message.reply_text("🎲 اول /manch رو بزن.")
        return
    if len(game["players"]) < 2:
        await update.message.reply_text("حداقل ۲ بازیکن لازم است.")
        return
    game["started"] = True
    game["turn"] = 0
    await update.message.reply_text(
        _manch_text(game), parse_mode="HTML", reply_markup=_manch_kb(game)
    )


# =========================================================
# 🪜 مار و پله
# =========================================================

def _snake_kb(game):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎲 تاس", callback_data=f"g5:s:d:{game['id']}"),
            InlineKeyboardButton("🚪 خروج", callback_data=f"g5:s:x:{game['id']}"),
        ]
    ])


def _snake_text(game):
    lines = [
        "🪜 <b>مار و پله گاتهام</b>",
        "",
        f"👑 نوبت: {_mention(game['players'][game['turn']])}",
        "",
    ]
    for u in game["players"]:
        lines.append(f"👤 {_mention(u)} — خانه {game['pos'][u.id]}")
    lines += ["", "🎲 تاس را بزن و به ۱۰۰ برس!"]
    return "\n".join(lines)


async def snake_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if gid in SNAKE:
        await update.message.reply_text("🪜 یک مار و پله همین الان در جریانه.")
        return
    SNAKE[gid] = {
        "id": str(gid),
        "players": [update.effective_user],
        "pos": {update.effective_user.id: 1},
        "turn": 0,
    }
    await update.message.reply_text(
        "🪜 <b>مار و پله گاتهام ساخته شد!</b>\n"
        "بازیکن بعدی: /joinsnake\n"
        "برای شروع: /startsnake\n\n"
        "هدف: رسیدن دقیق به خانه ۱۰۰.",
        parse_mode="HTML",
    )


async def join_snake_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    game = SNAKE.get(gid)
    if not game:
        await update.message.reply_text("🪜 اول /snake رو بزن.")
        return
    uid = update.effective_user.id
    if any(u.id == uid for u in game["players"]):
        await update.message.reply_text("تو از قبل داخل بازی هستی 😄")
        return
    if len(game["players"]) >= 6:
        await update.message.reply_text("ظرفیت این بازی ۶ نفره.")
        return
    game["players"].append(update.effective_user)
    game["pos"][uid] = 1
    await update.message.reply_text(
        f"✅ {_mention(update.effective_user)} وارد مار و پله شد!",
        parse_mode="HTML",
    )


async def start_snake_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    game = SNAKE.get(gid)
    if not game:
        await update.message.reply_text("🪜 اول /snake رو بزن.")
        return
    if len(game["players"]) < 2:
        await update.message.reply_text("حداقل ۲ بازیکن لازم است.")
        return
    await update.message.reply_text(
        _snake_text(game), parse_mode="HTML", reply_markup=_snake_kb(game)
    )


# =========================================================
# CALLBACKS
# =========================================================

async def games_pack5_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    parts = data.split(":")
    if len(parts) != 4 or parts[0] != "g5":
        return

    game_type, action, gid_s = parts[1], parts[2], parts[3]
    gid = int(gid_s)

    if action == "x":
        if game_type == "m":
            MANCH.pop(gid, None)
        elif game_type == "s":
            SNAKE.pop(gid, None)
        elif game_type == "c":
            CHESS.pop(gid, None)
        await q.edit_message_text("🚪 بازی گاتهام بسته شد.")
        return

    if action != "d":
        return

    user_id = q.from_user.id

    if game_type == "m":
        game = MANCH.get(gid)
        if not game or not game["started"]:
            return
        expected = game["players"][game["turn"]]
        if expected.id != user_id:
            await q.answer("⏳ نوبت تو نیست!", show_alert=True)
            return

        roll = random.randint(1, 6)
        pos = game["pos"][user_id]

        # قانون ساده منچ: برای ورود از صفر باید 6 بیاید.
        if pos == 0:
            if roll == 6:
                pos = 1
            else:
                msg = f"🎲 {_name(expected)} عدد <b>{roll}</b> آورد؛ مهره هنوز بیرون است."
                game["turn"] = (game["turn"] + 1) % len(game["players"])
                await q.edit_message_text(msg + "\n\n" + _manch_text(game), parse_mode="HTML", reply_markup=_manch_kb(game))
                return
        else:
            pos += roll
            if pos > 40:
                pos = 40

        game["pos"][user_id] = pos
        if pos >= 40:
            await q.edit_message_text(
                f"🏆 <b>{_mention(expected)} قهرمان منچ گاتهام شد!</b>\n"
                f"🎲 تاس: {roll}\n🏁 خانه نهایی: 40",
                parse_mode="HTML",
            )
            MANCH.pop(gid, None)
            return

        # تاس ۶ = یک نوبت اضافه
        if roll != 6:
            game["turn"] = (game["turn"] + 1) % len(game["players"])

        await q.edit_message_text(
            f"🎲 {_mention(expected)} → <b>{roll}</b>\n"
            f"📍 خانه فعلی: {pos}\n\n" + _manch_text(game),
            parse_mode="HTML",
            reply_markup=_manch_kb(game),
        )
        return

    if game_type == "s":
        game = SNAKE.get(gid)
        if not game:
            return
        expected = game["players"][game["turn"]]
        if expected.id != user_id:
            await q.answer("⏳ نوبت تو نیست!", show_alert=True)
            return

        roll = random.randint(1, 6)
        old = game["pos"][user_id]
        new = old + roll
        if new <= 100:
            new = LADDERS.get(new, SNAKES.get(new, new))
            game["pos"][user_id] = new

        if new == 100:
            await q.edit_message_text(
                f"🏆 <b>{_mention(expected)} برنده شد!</b>\n"
                f"🎲 تاس: {roll}\n🪜 گاتهام تسخیر شد!",
                parse_mode="HTML",
            )
            SNAKE.pop(gid, None)
            return

        game["turn"] = (game["turn"] + 1) % len(game["players"])
        event = ""
        if old + roll in LADDERS:
            event = f"\n🪜 نردبان! رفتی به {new}."
        elif old + roll in SNAKES:
            event = f"\n🐍 مار! برگشتی به {new}."

        await q.edit_message_text(
            f"🎲 {_mention(expected)} → <b>{roll}</b>\n"
            f"📍 {old} → {new}{event}\n\n" + _snake_text(game),
            parse_mode="HTML",
            reply_markup=_snake_kb(game),
        )
        return


# =========================================================
# ثبت هندلرها
# =========================================================

def register_games_pack5(app):
    app.add_handler(CommandHandler("manch", manch_cmd))
    app.add_handler(CommandHandler("joinmanch", join_manch_cmd))
    app.add_handler(CommandHandler("startmanch", start_manch_cmd))

    app.add_handler(CommandHandler("snake", snake_cmd))
    app.add_handler(CommandHandler("joinsnake", join_snake_cmd))
    app.add_handler(CommandHandler("startsnake", start_snake_cmd))


    app.add_handler(
        CallbackQueryHandler(games_pack5_callback, pattern=r"^g5:")
    )
