# -*- coding: utf-8 -*-
"""
ttt_gotham.py
================
نسخه‌ی «با کلمه شروع می‌شه» دوز چندسایزی — کلمه‌ی محرک: «دوز گاتهام»

برخلاف ttt_inline.py (که با @نام_ربات کار می‌کنه)، این نسخه عین بقیه‌ی بازی‌های
games.py با نوشتن یه کلمه تو خود چت فعال می‌شه، بعد یه منو برای انتخاب سایز برد
(۳×۳ تا ۸×۸) و حریف (با دوست / با ربات) نشون می‌ده.

منطق برد/برنده‌شدن/هوش‌مصنوعی از ttt_inline.py دوباره استفاده می‌شه (کد تکراری نداره).

نحوه‌ی اتصال:
  - تو games.py: از این فایل gotham_ttt_start رو ایمپورت کن و تو keyword_router
    وقتی متن == "دوز گاتهام" بود صداش بزن (و به GAME_TRIGGER_WORDS اضافه‌ش کن).
  - تو bot.py: register_ttt_gotham(app) رو تو main() صدا بزن.
"""

import asyncio
import random
import string

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from ttt_inline import new_board, win_length, check_winner, choose_ai_move, AI_ID, TURN_TIMEOUT_SECONDS

TRIGGER_TEXT = "دوز گاتهام"

GOTHAM_TTT_STATE = {}  # game_id -> state


def _new_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


def _save_game_record(chat_id, winner_id, loser_id):
    try:
        import bot as _bot
        _bot._record_game_result(chat_id, winner_id, loser_id)
    except Exception:
        pass


def size_mode_markup(creator_id):
    rows = []
    for n in range(3, 9):
        rows.append(
            [
                InlineKeyboardButton(f"{n}×{n} 👥 با دوست", callback_data=f"ttg:new:{creator_id}:{n}:pvp"),
                InlineKeyboardButton(f"{n}×{n} 🃏 با ربات", callback_data=f"ttg:new:{creator_id}:{n}:ai"),
            ]
        )
    return InlineKeyboardMarkup(rows)


async def gotham_ttt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    creator = update.effective_user
    await msg.reply_text(
        "🦇 دوز گاتهام\nسایز برد و حریف رو انتخاب کن:",
        reply_markup=size_mode_markup(creator.id),
    )


def _header_text(state):
    n = state["size"]
    x_id = [pid for pid, s in state["players"].items() if s == "X"][0]
    o_id = [pid for pid, s in state["players"].items() if s == "O"][0]
    return (
        f"🦇 دوز گاتهام {n}×{n}\n"
        f"{state['names'][x_id]} (🦇) در برابر {state['names'][o_id]} (🃏)\n"
        f"نوبت: {state['names'][state['turn']]}\n"
        f"⏰ {TURN_TIMEOUT_SECONDS} ثانیه وقت داری حرکت کنی."
    )


def _board_markup(state, game_id):
    n = state["size"]
    board = state["board"]
    symbols = {"": "▫️", "X": "🦇", "O": "🃏"}
    rows = []
    for r in range(n):
        row = []
        for c in range(n):
            i = r * n + c
            row.append(InlineKeyboardButton(symbols[board[i]], callback_data=f"ttg:m:{game_id}:{i}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


async def new_game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, _, creator_id_str, n_str, mode = query.data.split(":")
    creator_id = int(creator_id_str)
    n = int(n_str)

    if query.from_user.id != creator_id:
        await query.answer("این انتخاب رو فقط کسی که بازی رو شروع کرده می‌تونه بزنه.", show_alert=True)
        return

    win_len = win_length(n)
    creator_name = query.from_user.first_name
    game_id = _new_id()
    chat_id = query.message.chat.id

    if mode == "ai":
        state = {
            "size": n,
            "win_len": win_len,
            "mode": "ai",
            "board": new_board(n),
            "players": {creator_id: "X", AI_ID: "O"},
            "names": {creator_id: creator_name, AI_ID: "🃏 جوکر (ربات)"},
            "turn": creator_id,
            "move_no": 0,
            "chat_id": chat_id,
        }
        GOTHAM_TTT_STATE[game_id] = state
        await query.edit_message_text(_header_text(state), reply_markup=_board_markup(state, game_id))
        await query.answer()
        asyncio.create_task(_timeout_watch(game_id, 0, chat_id, context.bot))
    else:
        state = {
            "size": n,
            "win_len": win_len,
            "mode": "pvp",
            "board": None,
            "players": {creator_id: "X"},
            "names": {creator_id: creator_name},
            "creator_id": creator_id,
            "started": False,
            "chat_id": chat_id,
        }
        GOTHAM_TTT_STATE[game_id] = state
        text = f"🦇 {creator_name} می‌خواد دوز گاتهام {n}×{n} بازی کنه!\nحریف، دکمه‌ی زیر رو بزن تا بازی شروع بشه."
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🤝 بپیوند", callback_data=f"ttgj:{game_id}")]])
        await query.edit_message_text(text, reply_markup=markup)
        await query.answer()


async def join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, game_id = query.data.split(":")
    state = GOTHAM_TTT_STATE.get(game_id)
    if not state or state.get("started"):
        await query.answer("این دعوت دیگه معتبر نیست.", show_alert=True)
        return

    joiner = query.from_user
    if joiner.id == state["creator_id"]:
        await query.answer("نمی‌تونی با خودت بازی کنی 🙂", show_alert=True)
        return

    n = state["size"]
    state["board"] = new_board(n)
    state["players"][joiner.id] = "O"
    state["names"][joiner.id] = joiner.first_name
    state["turn"] = state["creator_id"]
    state["started"] = True
    state["move_no"] = 0

    await query.edit_message_text(_header_text(state), reply_markup=_board_markup(state, game_id))
    await query.answer()
    asyncio.create_task(_timeout_watch(game_id, 0, state["chat_id"], context.bot))


async def _finish(query, state, game_id, result_text, winner_id=None, loser_id=None):
    try:
        await query.edit_message_text(result_text, reply_markup=_board_markup(state, game_id))
    except Exception:
        pass
    await query.answer()
    if winner_id is not None and loser_id is not None and AI_ID not in (winner_id, loser_id):
        _save_game_record(state["chat_id"], winner_id, loser_id)
    GOTHAM_TTT_STATE.pop(game_id, None)


async def move_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, _, game_id, idx = query.data.split(":")
    idx = int(idx)
    state = GOTHAM_TTT_STATE.get(game_id)
    if not state or not state.get("board"):
        await query.answer("این بازی تموم شده.", show_alert=True)
        return

    user_id = query.from_user.id
    if user_id not in state["players"]:
        await query.answer("تو تو این بازی نیستی.", show_alert=True)
        return
    if state["turn"] != user_id:
        await query.answer("نوبت تو نیست.", show_alert=True)
        return
    if state["board"][idx]:
        await query.answer("این خونه پره.", show_alert=True)
        return

    n = state["size"]
    win_len = state["win_len"]
    state["board"][idx] = state["players"][user_id]
    state["move_no"] += 1

    result = check_winner(state["board"], n, win_len)
    other_id = [pid for pid in state["players"] if pid != user_id][0]

    if result == "draw":
        await _finish(query, state, game_id, "مساوی شد! 🤝")
        return
    if result:
        await _finish(query, state, game_id, f"🏆 {state['names'][user_id]} برد!", winner_id=user_id, loser_id=other_id)
        return

    if state["mode"] == "ai" and other_id == AI_ID:
        ai_symbol = state["players"][AI_ID]
        human_symbol = state["players"][user_id]
        ai_idx = choose_ai_move(state["board"], n, win_len, ai_symbol, human_symbol)
        if ai_idx is not None:
            state["board"][ai_idx] = ai_symbol
            state["move_no"] += 1
            result2 = check_winner(state["board"], n, win_len)
            if result2 == "draw":
                await _finish(query, state, game_id, "مساوی شد! 🤝")
                return
            if result2:
                await _finish(query, state, game_id, "🃏 جوکر (ربات) برد!")
                return
        state["turn"] = user_id
        try:
            await query.edit_message_text(_header_text(state), reply_markup=_board_markup(state, game_id))
        except Exception:
            pass
        await query.answer()
        return

    state["turn"] = other_id
    try:
        await query.edit_message_text(_header_text(state), reply_markup=_board_markup(state, game_id))
    except Exception:
        pass
    await query.answer()
    asyncio.create_task(_timeout_watch(game_id, state["move_no"], state["chat_id"], context.bot))


async def _timeout_watch(game_id, move_no, chat_id, bot):
    await asyncio.sleep(TURN_TIMEOUT_SECONDS)
    state = GOTHAM_TTT_STATE.get(game_id)
    if not state or state.get("move_no") != move_no or not state.get("board"):
        return
    loser_id = state["turn"]
    others = [pid for pid in state["players"] if pid != loser_id]
    if not others:
        return
    winner_id = others[0]
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=f"⏰ وقت {state['names'][loser_id]} تموم شد! {state['names'][winner_id]} با نبود حریف برنده شد.",
        )
    except Exception:
        pass
    if AI_ID not in (winner_id, loser_id):
        _save_game_record(chat_id, winner_id, loser_id)
    GOTHAM_TTT_STATE.pop(game_id, None)


def register_ttt_gotham(app):
    app.add_handler(CallbackQueryHandler(new_game_callback, pattern=r"^ttg:new:"), group=1)
    app.add_handler(CallbackQueryHandler(join_callback, pattern=r"^ttgj:"), group=1)
    app.add_handler(CallbackQueryHandler(move_callback, pattern=r"^ttg:m:"), group=1)
