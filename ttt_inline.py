# -*- coding: utf-8 -*-
"""
ttt_inline.py
================
دوز (Tic-Tac-Toe) نسخه‌ی inline: با نوشتن @نام_ربات تو هر چتی (حتی چت خصوصی یا
گروه‌هایی که ربات توشون عضو نیست) میشه بازی رو شروع کرد.

ویژگی‌ها:
  • بردهای ۳×۳ تا ۸×۸ (برای ۳×۳ سه‌تا پشت‌سرهم، ۴×۴ چهارتا، ۵×۸ پنج‌تا پشت‌سرهم می‌بره)
  • حالت با یه دوست (PvP) — نفر دوم با زدن دکمه‌ی «بپیوند» وارد بازی می‌شه
  • حالت با ربات — روی ۳×۳ هوش مصنوعی کاملاً غیرقابل‌شکست (مینیمکس کامل) بازی می‌کنه؛
    روی بردهای بزرگ‌تر (۴×۴ تا ۸×۸) چون محاسبه‌ی مینیمکس کامل عملاً غیرممکنه، از یه
    استراتژی قوی (اول برد رو ببند/بگیر، بعد مرکز رو ترجیح بده) استفاده می‌کنه — یعنی
    خیلی سخته ولی «تضمینیِ غیرقابل‌شکست» نیست.

نکته‌ی مهم برای راه‌اندازی: باید حالت inline ربات از طریق BotFather فعال بشه:
    BotFather -> /mybots -> ربات مورد نظر -> Bot Settings -> Inline Mode -> Turn on

نحوه‌ی اتصال (در bot.py):
    from ttt_inline import register_ttt_inline
    register_ttt_inline(app)
"""

import asyncio
import random
import string

from telegram import (
    Update,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ContextTypes,
    InlineQueryHandler,
    ChosenInlineResultHandler,
    CallbackQueryHandler,
)

TURN_TIMEOUT_SECONDS = 90
AI_ID = -1  # آیدی مصنوعی برای بازیکن هوش مصنوعی (هیچ‌وقت با آیدی واقعی تلگرام یکی نمی‌شه)

# token -> game state
INLINE_TTT_STATE = {}


def _new_token() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=10))


def win_length(n: int) -> int:
    if n == 3:
        return 3
    if n == 4:
        return 4
    return 5  # برای ۵×۵ تا ۸×۸ — به سبک گومکو، ۵ تا پشت‌سرهم می‌بره


def new_board(n: int):
    return [""] * (n * n)


def check_winner(board, n, win_len):
    def get(r, c):
        if 0 <= r < n and 0 <= c < n:
            return board[r * n + c]
        return None

    directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
    for r in range(n):
        for c in range(n):
            v = get(r, c)
            if not v:
                continue
            for dr, dc in directions:
                ok = True
                for k in range(1, win_len):
                    if get(r + dr * k, c + dc * k) != v:
                        ok = False
                        break
                if ok:
                    return v
    if all(board):
        return "draw"
    return None


def _minimax(board, n, win_len, ai_symbol, human_symbol, is_ai_turn):
    result = check_winner(board, n, win_len)
    if result == ai_symbol:
        return 1
    if result == human_symbol:
        return -1
    if result == "draw":
        return 0
    empties = [i for i, v in enumerate(board) if not v]
    if is_ai_turn:
        best = -999
        for i in empties:
            board[i] = ai_symbol
            best = max(best, _minimax(board, n, win_len, ai_symbol, human_symbol, False))
            board[i] = ""
        return best
    else:
        best = 999
        for i in empties:
            board[i] = human_symbol
            best = min(best, _minimax(board, n, win_len, ai_symbol, human_symbol, True))
            board[i] = ""
        return best


def choose_ai_move(board, n, win_len, ai_symbol, human_symbol):
    empties = [i for i, v in enumerate(board) if not v]
    if not empties:
        return None

    if n == 3:
        best_score = -999
        best_move = empties[0]
        for i in empties:
            board[i] = ai_symbol
            score = _minimax(board, n, win_len, ai_symbol, human_symbol, False)
            board[i] = ""
            if score > best_score:
                best_score = score
                best_move = i
        return best_move

    # بردهای بزرگ‌تر: 1) اگه می‌تونه ببره، ببره  2) اگه حریف داره می‌بره، جلوشو بگیر
    # 3) وگرنه نزدیک‌ترین خونه‌ی خالی به مرکز رو (با کمی تصادف) انتخاب کن
    for i in empties:
        board[i] = ai_symbol
        if check_winner(board, n, win_len) == ai_symbol:
            board[i] = ""
            return i
        board[i] = ""

    for i in empties:
        board[i] = human_symbol
        if check_winner(board, n, win_len) == human_symbol:
            board[i] = ""
            return i
        board[i] = ""

    center = (n - 1) / 2
    empties.sort(key=lambda i: abs(i // n - center) + abs(i % n - center))
    top = empties[: max(1, len(empties) // 4)]
    return random.choice(top)


def inline_board_markup(state, token):
    n = state["size"]
    board = state["board"]
    symbols = {"": "▫️", "X": "❌", "O": "⭕"}
    rows = []
    for r in range(n):
        row = []
        for c in range(n):
            i = r * n + c
            row.append(InlineKeyboardButton(symbols[board[i]], callback_data=f"itt:{token}:{i}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def header_text(state):
    n = state["size"]
    x_id = [pid for pid, s in state["players"].items() if s == "X"][0]
    o_id = [pid for pid, s in state["players"].items() if s == "O"][0]
    lines = [
        f"🎮 دوز {n}×{n}",
        f"{state['names'][x_id]} (❌) در برابر {state['names'][o_id]} (⭕)",
        f"نوبت: {state['names'][state['turn']]}",
        f"⏰ {TURN_TIMEOUT_SECONDS} ثانیه وقت داری حرکت کنی.",
    ]
    return "\n".join(lines)


# =========================================================
#  Inline query — لیست حالت‌ها (سایز برد × PvP/AI)
# =========================================================

async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.inline_query
    query_text = (q.query or "").strip()

    sizes = list(range(3, 9))
    if query_text.isdigit() and 3 <= int(query_text) <= 8:
        sizes = [int(query_text)]

    results = []
    for n in sizes:
        wl = win_length(n)
        win_desc = f"{wl} تا پشت‌سرهم می‌بره"
        results.append(
            InlineQueryResultArticle(
                id=f"ttt_{n}_pvp_{_new_token()}",
                title=f"🎮 دوز {n}×{n} — با یه دوست",
                description=f"یه نفر دیگه رو دعوت کن بازی کنه ({win_desc})",
                input_message_content=InputTextMessageContent(
                    f"🎮 در حال آماده‌سازی دوز {n}×{n} ..."
                ),
            )
        )
        results.append(
            InlineQueryResultArticle(
                id=f"ttt_{n}_ai_{_new_token()}",
                title=f"🤖 دوز {n}×{n} — در برابر ربات",
                description=f"تک‌نفره، در برابر هوش مصنوعی ({win_desc})",
                input_message_content=InputTextMessageContent(
                    f"🎮 در حال آماده‌سازی دوز {n}×{n} در برابر ربات ..."
                ),
            )
        )

    try:
        await q.answer(results, cache_time=0, is_personal=True)
    except Exception:
        pass


# =========================================================
#  Chosen result — همین که کاربر یه گزینه رو انتخاب کرد
# =========================================================

async def chosen_result_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chosen = update.chosen_inline_result
    imid = chosen.inline_message_id
    result_id = chosen.result_id
    if not imid or not result_id.startswith("ttt_"):
        return

    try:
        _, n_str, mode = result_id.split("_")[:3]
        n = int(n_str)
    except Exception:
        return

    creator = chosen.from_user
    win_len = win_length(n)
    token = _new_token()

    if mode == "ai":
        state = {
            "size": n,
            "win_len": win_len,
            "mode": "ai",
            "board": new_board(n),
            "players": {creator.id: "X", AI_ID: "O"},
            "names": {creator.id: creator.first_name, AI_ID: "🤖 ربات"},
            "turn": creator.id,
            "move_no": 0,
            "imid": imid,
        }
        INLINE_TTT_STATE[token] = state
        try:
            await context.bot.edit_message_text(
                inline_message_id=imid,
                text=header_text(state),
                reply_markup=inline_board_markup(state, token),
            )
        except Exception:
            pass
        asyncio.create_task(_inline_timeout_watch(token, 0, context.bot))
    else:
        state = {
            "size": n,
            "win_len": win_len,
            "mode": "pvp",
            "board": None,
            "players": {creator.id: "X"},
            "names": {creator.id: creator.first_name},
            "creator_id": creator.id,
            "started": False,
            "imid": imid,
        }
        INLINE_TTT_STATE[token] = state
        text = (
            f"🎮 {creator.first_name} می‌خواد دوز {n}×{n} بازی کنه!\n"
            f"حریف، دکمه‌ی زیر رو بزن تا بازی شروع بشه."
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🤝 بپیوند", callback_data=f"ittj:{token}")]])
        try:
            await context.bot.edit_message_text(inline_message_id=imid, text=text, reply_markup=markup)
        except Exception:
            pass


# =========================================================
#  پیوستن حریف دوم (فقط حالت PvP)
# =========================================================

async def join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, token = query.data.split(":")
    state = INLINE_TTT_STATE.get(token)
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

    await query.edit_message_text(header_text(state), reply_markup=inline_board_markup(state, token))
    await query.answer()
    asyncio.create_task(_inline_timeout_watch(token, 0, context.bot))


# =========================================================
#  حرکت رو خونه‌ها
# =========================================================

async def _finish(query, state, token, result_text):
    try:
        await query.edit_message_text(f"{result_text}", reply_markup=inline_board_markup(state, token))
    except Exception:
        pass
    await query.answer()
    INLINE_TTT_STATE.pop(token, None)


async def move_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, token, idx = query.data.split(":")
    idx = int(idx)
    state = INLINE_TTT_STATE.get(token)
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
        await _finish(query, state, token, "مساوی شد! 🤝")
        return
    if result:
        await _finish(query, state, token, f"🏆 {state['names'][user_id]} برد!")
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
                await _finish(query, state, token, "مساوی شد! 🤝")
                return
            if result2:
                await _finish(query, state, token, "🤖 ربات برد!")
                return
        state["turn"] = user_id
        try:
            await query.edit_message_text(header_text(state), reply_markup=inline_board_markup(state, token))
        except Exception:
            pass
        await query.answer()
        return

    state["turn"] = other_id
    try:
        await query.edit_message_text(header_text(state), reply_markup=inline_board_markup(state, token))
    except Exception:
        pass
    await query.answer()
    asyncio.create_task(_inline_timeout_watch(token, state["move_no"], context.bot))


async def _inline_timeout_watch(token, move_no, bot):
    await asyncio.sleep(TURN_TIMEOUT_SECONDS)
    state = INLINE_TTT_STATE.get(token)
    if not state or state.get("move_no") != move_no or not state.get("board"):
        return
    loser_id = state["turn"]
    others = [pid for pid in state["players"] if pid != loser_id]
    if not others:
        return
    winner_id = others[0]
    imid = state.get("imid")
    try:
        await bot.edit_message_text(
            inline_message_id=imid,
            text=f"⏰ وقت {state['names'][loser_id]} تموم شد! {state['names'][winner_id]} با نبود حریف برنده شد.",
        )
    except Exception:
        pass
    INLINE_TTT_STATE.pop(token, None)


# =========================================================
#  ثبت هندلرها
# =========================================================

def register_ttt_inline(app):
    app.add_handler(InlineQueryHandler(inline_query_handler), group=1)
    app.add_handler(ChosenInlineResultHandler(chosen_result_handler), group=1)
    app.add_handler(CallbackQueryHandler(join_callback, pattern=r"^ittj:"), group=1)
    app.add_handler(CallbackQueryHandler(move_callback, pattern=r"^itt:"), group=1)
