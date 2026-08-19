# -*- coding: utf-8 -*-
"""Professional board games for Gotham Telegram Bot.

Games:
- Chess: real legal move validation via python-chess.
- Ludo: 2-4 players, dice, four pieces, capture/safe squares and exact finish.
- Snakes & Ladders: 2-4 players, 1-100 board, snakes/ladders and exact finish.

All state is in memory for the current bot process. A restart ends active games.
"""
import random
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

try:
    import chess
except ImportError:  # helpful startup message if dependency was forgotten
    chess = None


CHESS_GAMES: Dict[str, dict] = {}
LUDO_GAMES: Dict[str, dict] = {}
SNAKES_GAMES: Dict[str, dict] = {}

COLORS = ["🔴", "🟢", "🟡", "🔵"]
LUDO_SAFE = {0, 8, 13, 21, 26, 34, 39, 47}
LUDO_START = [0, 13, 26, 39]
LUDO_FINISH = 57

SNAKES = {99: 54, 95: 75, 92: 88, 89: 68, 74: 53, 64: 60, 62: 19, 49: 11, 47: 26, 16: 6}
LADDERS = {2: 38, 7: 14, 8: 31, 15: 26, 21: 42, 28: 84, 36: 44, 51: 67, 71: 91, 78: 98}


def _gid(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:8]


def _name(user) -> str:
    return user.first_name or user.username or "بازیکن"


def _join_markup(prefix: str, gid: str, count: int = 4):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ پیوستن", callback_data=f"{prefix}:join:{gid}")],
        [InlineKeyboardButton("🚀 شروع بازی", callback_data=f"{prefix}:start:{gid}"),
         InlineKeyboardButton("❌ لغو", callback_data=f"{prefix}:cancel:{gid}")],
    ])


# ============================== CHESS ==============================

def _chess_board_text(board, selected=None):
    rows = ["♟️ شطرنج گاتهام", ""]
    for rank in range(7, -1, -1):
        cells = []
        for file in range(8):
            sq = chess.square(file, rank)
            piece = board.piece_at(sq)
            symbol = piece.unicode_symbol() if piece else "·"
            if selected == sq:
                symbol = f"【{symbol}】"
            cells.append(symbol)
        rows.append(f"{rank+1}  " + " ".join(cells))
    rows.append("    a  b  c  d  e  f  g  h")
    rows.append("")
    rows.append("با زدن خانهٔ مبدأ و سپس مقصد، حرکت کن.")
    return "\n".join(rows)


def _chess_markup(gid, board, selected=None):
    game = CHESS_GAMES[gid]
    rows = []
    for rank in range(7, -1, -1):
        row = []
        for file in range(8):
            sq = chess.square(file, rank)
            piece = board.piece_at(sq)
            label = piece.unicode_symbol() if piece else "·"
            if selected == sq:
                label = "🟣" + label
            row.append(InlineKeyboardButton(label, callback_data=f"chess:sq:{gid}:{sq}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("🔄 تازه‌سازی", callback_data=f"chess:refresh:{gid}"),
                 InlineKeyboardButton("🏳️ تسلیم", callback_data=f"chess:resign:{gid}")])
    return InlineKeyboardMarkup(rows)


async def chess_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    gid = _gid("ch")
    user = update.effective_user
    CHESS_GAMES[gid] = {
        "chat_id": chat_id, "players": [user.id], "names": {user.id: _name(user)},
        "board": chess.Board() if chess else None, "selected": None, "started": False,
    }
    text = "♟️ شطرنج گاتهام\n\n" f"👤 سفید: {_name(user)}\n" "👤 سیاه: منتظر حریف...\n\n" "نفر دوم روی «پیوستن» بزند."
    await update.effective_message.reply_text(text, reply_markup=_join_markup("chess", gid, 2))


async def _chess_callback(update, context):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    action, gid = parts[1], parts[2]
    game = CHESS_GAMES.get(gid)
    if not game:
        await q.answer("این بازی دیگر وجود ندارد.", show_alert=True); return
    uid = update.effective_user.id
    if action == "join":
        if uid in game["players"]:
            await q.answer("تو همین الان داخل بازی هستی.", show_alert=True); return
        if len(game["players"]) >= 2:
            await q.answer("این شطرنج پر شده.", show_alert=True); return
        game["players"].append(uid); game["names"][uid] = _name(update.effective_user)
        await q.edit_message_text(
            f"♟️ شطرنج گاتهام\n\n👤 سفید: {game['names'][game['players'][0]]}\n👤 سیاه: {game['names'][uid]}\n\nآماده‌اید؟",
            reply_markup=_join_markup("chess", gid, 2),
        ); return
    if action == "start":
        if uid != game["players"][0] or len(game["players"]) != 2:
            await q.answer("فقط سازنده و وقتی دو نفر حاضرند می‌تواند شروع کند.", show_alert=True); return
        game["started"] = True
        await _chess_render(q, gid); return
    if action == "cancel":
        if uid != game["players"][0]:
            await q.answer("فقط سازنده می‌تواند لغو کند.", show_alert=True); return
        del CHESS_GAMES[gid]
        await q.edit_message_text("♟️ بازی شطرنج لغو شد."); return
    if action == "refresh":
        await _chess_render(q, gid); return
    if action == "resign":
        if uid not in game["players"] or not game["started"]:
            return
        winner = game["players"][1] if uid == game["players"][0] else game["players"][0]
        await q.edit_message_text(f"🏳️ {_name(update.effective_user)} تسلیم شد!\n🏆 برنده: {game['names'][winner]}")
        del CHESS_GAMES[gid]; return
    if action == "sq":
        sq = int(parts[3])
        if not game["started"] or uid not in game["players"]:
            await q.answer("این بازی برای تو نیست.", show_alert=True); return
        board = game["board"]
        color_uid = game["players"][0] if board.turn == chess.WHITE else game["players"][1]
        if uid != color_uid:
            await q.answer("الان نوبت حریفه.", show_alert=True); return
        selected = game.get("selected")
        if selected is None:
            piece = board.piece_at(sq)
            if not piece or piece.color != board.turn:
                await q.answer("اول مهره‌ی خودت رو انتخاب کن.", show_alert=True); return
            game["selected"] = sq
            await _chess_render(q, gid); return
        move = chess.Move(selected, sq)
        if move not in board.legal_moves:
            # promotion shortcut: if pawn reaches last rank, auto-queen
            piece = board.piece_at(selected)
            if piece and piece.piece_type == chess.PAWN and chess.square_rank(sq) in (0, 7):
                move = chess.Move(selected, sq, promotion=chess.QUEEN)
        if move not in board.legal_moves:
            if board.piece_at(sq) and board.piece_at(sq).color == board.turn:
                game["selected"] = sq
                await _chess_render(q, gid)
            else:
                game["selected"] = None
                await q.answer("این حرکت قانونی نیست.", show_alert=True)
            return
        board.push(move); game["selected"] = None
        if board.is_checkmate():
            winner = game["names"][uid]
            await q.edit_message_text(f"♟️ کیش‌ومات!\n\n🏆 برنده: {winner}\n🎉 بازی تمام شد.")
            del CHESS_GAMES[gid]; return
        if board.is_stalemate() or board.is_insufficient_material() or board.is_fifty_moves():
            await q.edit_message_text("🤝 بازی مساوی شد!\nموقعیت دیگر ادامه‌ی برد ندارد.")
            del CHESS_GAMES[gid]; return
        await _chess_render(q, gid)


async def _chess_render(q, gid):
    game = CHESS_GAMES[gid]; board = game["board"]
    turn_uid = game["players"][0] if board.turn == chess.WHITE else game["players"][1]
    turn_name = game["names"][turn_uid]
    text = _chess_board_text(board, game.get("selected")) + f"\n\n🔔 نوبت: {turn_name}"
    if board.is_check(): text += "\n⚠️ کیش!"
    await q.edit_message_text(text, reply_markup=_chess_markup(gid, board, game.get("selected")))


# ============================== LUDO ==============================

def _ludo_abs(player_index, progress):
    if progress < 0 or progress >= 52: return None
    return (LUDO_START[player_index] + progress) % 52


def _ludo_text(game):
    lines = ["🎲 منچ گاتهام", ""]
    for i, uid in enumerate(game["players"]):
        pieces = game["pieces"][uid]
        vals = ["🏠" if p < 0 else "🏆" if p >= LUDO_FINISH else str(p) for p in pieces]
        lines.append(f"{COLORS[i]} {game['names'][uid]}: " + " | ".join(vals))
    if game["started"]:
        uid = game["players"][game["turn"]]
        lines += ["", f"🎯 نوبت: {game['names'][uid]}", f"🎲 تاس: {game['roll'] if game['roll'] else '—'}"]
    return "\n".join(lines)


def _ludo_markup(gid, game):
    rows = []
    if not game["started"]:
        rows = [[InlineKeyboardButton("➕ پیوستن", callback_data=f"ludo:join:{gid}")],
                [InlineKeyboardButton("🚀 شروع بازی", callback_data=f"ludo:start:{gid}"), InlineKeyboardButton("❌ لغو", callback_data=f"ludo:cancel:{gid}")]]
    else:
        uid = game["players"][game["turn"]]
        if game["roll"] is None:
            rows.append([InlineKeyboardButton("🎲 انداختن تاس", callback_data=f"ludo:roll:{gid}")])
        else:
            movable = [i for i in range(4) if _ludo_can_move(game, uid, i, game["roll"])]
            rows.append([InlineKeyboardButton(f"مهره {i+1}", callback_data=f"ludo:move:{gid}:{i}") for i in movable] or [InlineKeyboardButton("⏭️ رد نوبت", callback_data=f"ludo:pass:{gid}")])
        rows.append([InlineKeyboardButton("🏳️ خروج", callback_data=f"ludo:leave:{gid}")])
    return InlineKeyboardMarkup(rows)


def _ludo_can_move(game, uid, idx, roll):
    p = game["pieces"][uid][idx]
    if p >= LUDO_FINISH: return False
    if p < 0: return roll == 6
    return p + roll <= LUDO_FINISH


def _ludo_move(game, uid, idx, roll):
    p = game["pieces"][uid][idx]
    if p < 0: new = 0
    else: new = p + roll
    game["pieces"][uid][idx] = new
    if 0 <= new < 52:
        absolute = _ludo_abs(game["players"].index(uid), new)
        if absolute not in LUDO_SAFE:
            for other in game["players"]:
                if other == uid: continue
                for j, op in enumerate(game["pieces"][other]):
                    if 0 <= op < 52 and _ludo_abs(game["players"].index(other), op) == absolute:
                        game["pieces"][other][j] = -1


async def ludo_start(update, context):
    uid = update.effective_user.id; gid = _gid("lu")
    LUDO_GAMES[gid] = {"chat_id": update.effective_chat.id, "players": [uid], "names": {uid: _name(update.effective_user)}, "pieces": {uid: [-1]*4}, "turn": 0, "roll": None, "started": False}
    await update.effective_message.reply_text(f"🎲 منچ گاتهام\n\n🔴 {_name(update.effective_user)}\n🟢 منتظر بازیکن‌های دیگر...\n\n۲ تا ۴ نفر می‌توانند وارد شوند.", reply_markup=_join_markup("ludo", gid))


async def _ludo_callback(update, context):
    q = update.callback_query; await q.answer(); p = q.data.split(":"); action, gid = p[1], p[2]
    game = LUDO_GAMES.get(gid)
    if not game: await q.answer("این بازی تمام شده.", show_alert=True); return
    uid = update.effective_user.id
    if action == "join":
        if uid in game["players"]: await q.answer("قبلاً وارد شدی.", show_alert=True); return
        if game["started"] or len(game["players"]) >= 4: await q.answer("ورود ممکن نیست.", show_alert=True); return
        game["players"].append(uid); game["names"][uid] = _name(update.effective_user); game["pieces"][uid] = [-1]*4
        await q.edit_message_text(_ludo_text(game), reply_markup=_ludo_markup(gid, game)); return
    if action == "start":
        if uid != game["players"][0] or len(game["players"]) < 2: await q.answer("حداقل ۲ نفر لازم است و فقط سازنده شروع می‌کند.", show_alert=True); return
        game["started"] = True; await q.edit_message_text(_ludo_text(game), reply_markup=_ludo_markup(gid, game)); return
    if action == "cancel":
        if uid != game["players"][0]: return
        del LUDO_GAMES[gid]; await q.edit_message_text("🎲 منچ لغو شد."); return
    if not game["started"]: return
    if uid != game["players"][game["turn"]]: await q.answer("نوبت تو نیست.", show_alert=True); return
    if action == "roll":
        if game["roll"] is not None: await q.answer("اول مهره رو حرکت بده.", show_alert=True); return
        roll = random.randint(1,6); game["roll"] = roll
        movable = [i for i in range(4) if _ludo_can_move(game, uid, i, roll)]
        if not movable:
            game["roll"] = None; game["turn"] = (game["turn"] + (0 if roll == 6 else 1)) % len(game["players"])
            await q.edit_message_text(_ludo_text(game) + f"\n\n😅 تاس {roll} آمد؛ حرکتی نداری.", reply_markup=_ludo_markup(gid, game)); return
        await q.edit_message_text(_ludo_text(game) + f"\n\n🎲 عدد تاس: {roll}\nمهره‌ات را انتخاب کن.", reply_markup=_ludo_markup(gid, game)); return
    if action == "move":
        idx = int(p[3]); roll = game["roll"]
        if roll is None or not _ludo_can_move(game, uid, idx, roll): await q.answer("حرکت مجاز نیست.", show_alert=True); return
        _ludo_move(game, uid, idx, roll)
        won = all(x >= LUDO_FINISH for x in game["pieces"][uid])
        extra = roll == 6
        game["roll"] = None
        if won:
            await q.edit_message_text(f"🎲 منچ تمام شد!\n\n🏆 برنده: {game['names'][uid]}\n🔥 هر چهار مهره به خانه رسیدند!")
            del LUDO_GAMES[gid]; return
        if not extra: game["turn"] = (game["turn"] + 1) % len(game["players"])
        await q.edit_message_text(_ludo_text(game), reply_markup=_ludo_markup(gid, game)); return
    if action == "pass":
        game["roll"] = None; game["turn"] = (game["turn"] + 1) % len(game["players"]); await q.edit_message_text(_ludo_text(game), reply_markup=_ludo_markup(gid, game)); return
    if action == "leave":
        if len(game["players"]) <= 2: del LUDO_GAMES[gid]; await q.edit_message_text("🎲 بازی منچ پایان یافت."); return
        idx = game["players"].index(uid); game["players"].remove(uid); del game["pieces"][uid]; game["names"].pop(uid, None); game["turn"] %= len(game["players"]); await q.edit_message_text(_ludo_text(game), reply_markup=_ludo_markup(gid, game))


# ========================== SNAKES & LADDERS ==========================

def _snakes_text(game):
    lines = ["🐍 مار و پله گاتهام", "", "نردبان‌ها: " + "، ".join(f"{a}→{b}" for a,b in LADDERS.items()), "مارها: " + "، ".join(f"{a}→{b}" for a,b in SNAKES.items()), ""]
    for i, uid in enumerate(game["players"]): lines.append(f"{COLORS[i]} {game['names'][uid]}: خانه {game['pos'][uid]}")
    if game["started"]: lines.append(f"\n🎯 نوبت: {game['names'][game['players'][game['turn']]]}")
    return "\n".join(lines)


def _snakes_markup(gid, game):
    if not game["started"]:
        return _join_markup("snake", gid)
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎲 تاس", callback_data=f"snake:roll:{gid}")], [InlineKeyboardButton("🏳️ خروج", callback_data=f"snake:leave:{gid}")]])


async def snakes_start(update, context):
    uid = update.effective_user.id; gid = _gid("sn")
    SNAKES_GAMES[gid] = {"chat_id": update.effective_chat.id, "players": [uid], "names": {uid:_name(update.effective_user)}, "pos": {uid:0}, "turn":0, "started":False}
    await update.effective_message.reply_text("🐍 مار و پله گاتهام\n\n۲ تا ۴ نفره\nنفرات با «پیوستن» وارد شوند.", reply_markup=_join_markup("snake", gid))


async def _snake_callback(update, context):
    q=update.callback_query; await q.answer(); p=q.data.split(":"); action,gid=p[1],p[2]; game=SNAKES_GAMES.get(gid)
    if not game: await q.answer("این بازی تمام شده.", show_alert=True); return
    uid=update.effective_user.id
    if action=="join":
        if uid in game["players"] or game["started"] or len(game["players"])>=4: return
        game["players"].append(uid); game["names"][uid]=_name(update.effective_user); game["pos"][uid]=0; await q.edit_message_text(_snakes_text(game), reply_markup=_snakes_markup(gid,game)); return
    if action=="start":
        if uid!=game["players"][0] or len(game["players"])<2: await q.answer("حداقل ۲ نفر لازم است.",show_alert=True); return
        game["started"]=True; await q.edit_message_text(_snakes_text(game), reply_markup=_snakes_markup(gid,game)); return
    if action=="cancel":
        if uid==game["players"][0]: del SNAKES_GAMES[gid]; await q.edit_message_text("🐍 بازی لغو شد."); return
    if not game["started"] or uid!=game["players"][game["turn"]]: await q.answer("نوبت تو نیست.",show_alert=True); return
    if action=="roll":
        roll=random.randint(1,6); old=game["pos"][uid]; new=old+roll
        if new<=100:
            new=LADDERS.get(new,SNAKES.get(new,new)); game["pos"][uid]=new
        if new==100:
            await q.edit_message_text(f"🐍 مار و پله تمام شد!\n\n🏆 برنده: {game['names'][uid]}\n🎲 تاس: {roll}\n📍 {old} → {new}"); del SNAKES_GAMES[gid]; return
        game["turn"]=(game["turn"]+1)%len(game["players"])
        await q.edit_message_text(_snakes_text(game)+f"\n\n🎲 {game['names'][uid]} عدد {roll} آورد: {old} → {new}", reply_markup=_snakes_markup(gid,game)); return
    if action=="leave":
        if len(game["players"])<=2: del SNAKES_GAMES[gid]; await q.edit_message_text("🐍 بازی پایان یافت."); return
        game["players"].remove(uid); game["names"].pop(uid,None); game["pos"].pop(uid,None); game["turn"]%=len(game["players"]); await q.edit_message_text(_snakes_text(game), reply_markup=_snakes_markup(gid,game))


# ============================== ROUTER ==============================

async def board_game_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text=(update.effective_message.text or "").strip().lower()
    if text in {"شطرنج", "بازی شطرنج", "♟️ شطرنج"}:
        if chess is None:
            await update.effective_message.reply_text("⚠️ موتور شطرنج نصب نشده. requirements.txt را به‌روزرسانی کن.")
        else:
            await chess_start(update, context)
    elif text in {"منچ", "بازی منچ", "🎲 منچ"}:
        await ludo_start(update, context)
    elif text in {"مار و پله", "ماروپله", "بازی مار و پله", "🐍 مار و پله"}:
        await snakes_start(update, context)


def register_board_games(app):
    app.add_handler(CallbackQueryHandler(_chess_callback, pattern=r"^chess:"), group=1)
    app.add_handler(CallbackQueryHandler(_ludo_callback, pattern=r"^ludo:"), group=1)
    app.add_handler(CallbackQueryHandler(_snake_callback, pattern=r"^snake:"), group=1)
    # نکته‌ی مهم: این نباید group=1 باشه، چون keyword_router تو games.py هم یه
    # MessageHandler(filters.TEXT & ~filters.COMMAND) با group=1 داره؛ تو یه گروه،
    # فقط اولین هندلری که فیلترش match بشه اجرا می‌شه (فیلتر TEXT خام همیشه match
    # می‌شه)، پس این هندلر هیچ‌وقت اجرا نمی‌شد. باید تو گروه اختصاصی خودش باشه.
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, board_game_router), group=11)
