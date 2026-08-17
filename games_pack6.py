# games_pack6.py
# 🦇 Gotham Chess — شطرنج حرفه‌ای برای تلگرام
#
# امکانات:
# ♟️ صفحه ۸×۸ با دکمه‌های قابل لمس
# ♟️ حرکت قانونی مهره‌ها
# ♟️ کیش / کیش‌ومات / پات
# ♟️ قلعه کوتاه و بلند
# ♟️ آن‌پاسان
# ♟️ ارتقای پیاده
# ♟️ گرفتن مهره
# ♟️ نوبت و رنگ مشخص
# ♟️ بازی خصوصی در گروه
#
# اتصال:
#   from games_pack6 import register_games_pack6
#   register_games_pack6(app)

import copy
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler


# =========================================================
# GAME STATE
# =========================================================

CHESS6 = {}

FILES = "abcdefgh"
RANKS = "12345678"

UNICODE = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
}

START = [
    list("rnbqkbnr"),
    list("pppppppp"),
    list("........"),
    list("........"),
    list("........"),
    list("........"),
    list("PPPPPPPP"),
    list("RNBQKBNR"),
]


def _name(u):
    return u.first_name or u.username or str(u.id)


def _mention(u):
    return f'<a href="tg://user?id={u.id}">{_name(u)}</a>'


def _initial_state(gid, white):
    return {
        "id": str(gid),
        "players": [white],
        "board": copy.deepcopy(START),
        "turn": True,                 # True = white
        "selected": None,
        "en_passant": None,           # (row, col) target square
        "castle": {
            "K": True, "Q": True,
            "k": True, "q": True,
        },
        "halfmove": 0,
        "moves": [],
        "captured_white": [],
        "captured_black": [],
        "status": "waiting",
    }


# =========================================================
# BOARD / SQUARE HELPERS
# =========================================================

def sq_to_rc(s):
    s = s.lower()
    if len(s) != 2 or s[0] not in FILES or s[1] not in RANKS:
        return None
    return 8 - int(s[1]), FILES.index(s[0])


def rc_to_sq(r, c):
    return f"{FILES[c]}{8-r}"


def inside(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def is_white(piece):
    return piece != "." and piece.isupper()


def same_side(piece, white):
    return piece != "." and is_white(piece) == white


def enemy(piece, white):
    return piece != "." and is_white(piece) != white


def find_king(board, white):
    target = "K" if white else "k"
    for r in range(8):
        for c in range(8):
            if board[r][c] == target:
                return r, c
    return None


# =========================================================
# ATTACK / CHECK
# =========================================================

def square_attacked(board, tr, tc, by_white):
    # Pawns
    pawn = "P" if by_white else "p"
    pr = tr + 1 if by_white else tr - 1
    for dc in (-1, 1):
        pc = tc + dc
        if inside(pr, pc) and board[pr][pc] == pawn:
            return True

    # Knights
    knight = "N" if by_white else "n"
    for dr, dc in ((-2,-1),(-2,1),(-1,-2),(-1,2),
                   (1,-2),(1,2),(2,-1),(2,1)):
        r, c = tr + dr, tc + dc
        if inside(r, c) and board[r][c] == knight:
            return True

    # Kings
    king = "K" if by_white else "k"
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            r, c = tr + dr, tc + dc
            if inside(r, c) and board[r][c] == king:
                return True

    # Sliding pieces
    bishop = "B" if by_white else "b"
    rook = "R" if by_white else "r"
    queen = "Q" if by_white else "q"

    for dr, dc in ((1,1),(1,-1),(-1,1),(-1,-1)):
        r, c = tr + dr, tc + dc
        while inside(r, c):
            p = board[r][c]
            if p != ".":
                if p in (bishop, queen):
                    return True
                break
            r += dr
            c += dc

    for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
        r, c = tr + dr, tc + dc
        while inside(r, c):
            p = board[r][c]
            if p != ".":
                if p in (rook, queen):
                    return True
                break
            r += dr
            c += dc

    return False


def in_check(board, white):
    king = find_king(board, white)
    return king is None or square_attacked(board, king[0], king[1], not white)


# =========================================================
# MOVE GENERATION
# =========================================================

def pseudo_moves(game, fr, fc):
    board = game["board"]
    p = board[fr][fc]
    if p == ".":
        return []

    white = is_white(p)
    kind = p.lower()
    out = []

    def add(r, c):
        if inside(r, c) and not same_side(board[r][c], white):
            out.append((r, c))

    if kind == "p":
        d = -1 if white else 1
        start = 6 if white else 1

        if inside(fr+d, fc) and board[fr+d][fc] == ".":
            out.append((fr+d, fc))
            if fr == start and board[fr+2*d][fc] == ".":
                out.append((fr+2*d, fc))

        for dc in (-1, 1):
            r, c = fr+d, fc+dc
            if not inside(r, c):
                continue
            if enemy(board[r][c], white):
                out.append((r, c))
            elif game["en_passant"] == (r, c):
                out.append((r, c))

    elif kind == "n":
        for dr, dc in ((-2,-1),(-2,1),(-1,-2),(-1,2),
                       (1,-2),(1,2),(2,-1),(2,1)):
            add(fr+dr, fc+dc)

    elif kind in ("b", "r", "q"):
        dirs = []
        if kind in ("b", "q"):
            dirs += [(1,1),(1,-1),(-1,1),(-1,-1)]
        if kind in ("r", "q"):
            dirs += [(1,0),(-1,0),(0,1),(0,-1)]

        for dr, dc in dirs:
            r, c = fr+dr, fc+dc
            while inside(r, c):
                if board[r][c] == ".":
                    out.append((r, c))
                else:
                    if enemy(board[r][c], white):
                        out.append((r, c))
                    break
                r += dr
                c += dc

    elif kind == "k":
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr or dc:
                    add(fr+dr, fc+dc)

        # Castling
        row = 7 if white else 0
        if (fr, fc) == (row, 4) and not in_check(board, white):
            rights = ("K", "Q") if white else ("k", "q")

            # King side
            if game["castle"][rights[0]]:
                if board[row][5] == "." and board[row][6] == ".":
                    if not square_attacked(board, row, 5, not white) and not square_attacked(board, row, 6, not white):
                        out.append((row, 6))

            # Queen side
            if game["castle"][rights[1]]:
                if board[row][1] == "." and board[row][2] == "." and board[row][3] == ".":
                    if not square_attacked(board, row, 3, not white) and not square_attacked(board, row, 2, not white):
                        out.append((row, 2))

    return out


def apply_move_copy(game, fr, fc, tr, tc):
    g = copy.deepcopy(game)
    board = g["board"]
    p = board[fr][fc]
    captured = board[tr][tc]
    white = is_white(p)

    # En-passant capture
    if p.lower() == "p" and (tr, tc) == g["en_passant"] and captured == "." and fc != tc:
        cap_r = tr + (1 if white else -1)
        board[cap_r][tc] = "."

    # Move piece
    board[tr][tc] = p
    board[fr][fc] = "."

    # Castling rook
    if p.lower() == "k" and abs(tc-fc) == 2:
        row = fr
        if tc == 6:
            board[row][5] = board[row][7]
            board[row][7] = "."
        else:
            board[row][3] = board[row][0]
            board[row][0] = "."

    # Promotion to queen by default.
    if p == "P" and tr == 0:
        board[tr][tc] = "Q"
    elif p == "p" and tr == 7:
        board[tr][tc] = "q"

    # Update castling rights after king/rook movement or rook capture.
    if p == "K":
        g["castle"]["K"] = g["castle"]["Q"] = False
    elif p == "k":
        g["castle"]["k"] = g["castle"]["q"] = False
    elif p == "R":
        if (fr, fc) == (7, 0): g["castle"]["Q"] = False
        if (fr, fc) == (7, 7): g["castle"]["K"] = False
    elif p == "r":
        if (fr, fc) == (0, 0): g["castle"]["q"] = False
        if (fr, fc) == (0, 7): g["castle"]["k"] = False

    if captured == "R":
        if (tr, tc) == (7, 0): g["castle"]["Q"] = False
        if (tr, tc) == (7, 7): g["castle"]["K"] = False
    elif captured == "r":
        if (tr, tc) == (0, 0): g["castle"]["q"] = False
        if (tr, tc) == (0, 7): g["castle"]["k"] = False

    # New en-passant square only after a two-square pawn move.
    g["en_passant"] = None
    if p.lower() == "p" and abs(tr-fr) == 2:
        g["en_passant"] = ((fr+tr)//2, fc)

    g["turn"] = not white
    return g


def legal_moves_from(game, fr, fc):
    p = game["board"][fr][fc]
    if p == ".":
        return []

    white = is_white(p)
    result = []
    for tr, tc in pseudo_moves(game, fr, fc):
        g = apply_move_copy(game, fr, fc, tr, tc)
        if not in_check(g["board"], white):
            result.append((tr, tc))
    return result


def all_legal_moves(game, white):
    moves = []
    board = game["board"]
    for r in range(8):
        for c in range(8):
            if same_side(board[r][c], white):
                for tr, tc in legal_moves_from(game, r, c):
                    moves.append((r, c, tr, tc))
    return moves


# =========================================================
# BOARD UI
# =========================================================

def board_text(game):
    board = game["board"]
    rows = ["♟️ <b>GOTHAM CHESS</b>", ""]
    for r in range(8):
        cells = []
        for c in range(8):
            p = board[r][c]
            cells.append(UNICODE[p] if p != "." else "·")
        rows.append(f"<b>{8-r}</b>  " + " ".join(cells))
    rows.append("    a b c d e f g h")
    return "\n".join(rows)


def board_keyboard(game):
    buttons = []
    selected = game["selected"]
    legal = set(legal_moves_from(game, *selected)) if selected else set()

    for r in range(8):
        row = []
        for c in range(8):
            p = game["board"][r][c]
            label = UNICODE[p] if p != "." else "·"
            if (r, c) in legal:
                label = "🟢" + label
            elif selected == (r, c):
                label = "🔵" + label
            row.append(
                InlineKeyboardButton(
                    label,
                    callback_data=f"g6:m:{game['id']}:{r}:{c}"
                )
            )
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton("🔄 تازه‌سازی", callback_data=f"g6:r:{game['id']}"),
        InlineKeyboardButton("🏳️ تسلیم", callback_data=f"g6:q:{game['id']}"),
    ])
    return InlineKeyboardMarkup(buttons)


def game_status(game):
    white = game["turn"]
    moves = all_legal_moves(game, white)
    if not moves:
        if in_check(game["board"], white):
            return "♚ <b>کیش‌ومات!</b>"
        return "🤝 <b>پات — مساوی!</b>"
    if in_check(game["board"], white):
        return "⚠️ <b>کیش!</b>"
    return "♙ نوبت حرکت"


# =========================================================
# COMMANDS
# =========================================================

async def chess6_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if gid in CHESS6:
        await update.message.reply_text("♟️ یک شطرنج گاتهام در این گروه در جریانه.")
        return

    game = _initial_state(gid, update.effective_user)
    CHESS6[gid] = game

    await update.message.reply_text(
        "🦇 <b>GOTHAM CHESS — بازی جدید</b>\n\n"
        f"⚪ سفید: {_mention(update.effective_user)}\n"
        "⚫ سیاه: منتظر بازیکن...\n\n"
        "بازیکن دوم برای ورود بزند: <code>/joinchess6</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🚪 لغو بازی", callback_data=f"g6:x:{gid}")
        ]]),
    )


async def join_chess6_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    game = CHESS6.get(gid)
    if not game:
        await update.message.reply_text("♟️ اول /chess6 رو بزن.")
        return
    if len(game["players"]) >= 2:
        await update.message.reply_text("این شطرنج دو بازیکن داره.")
        return
    if update.effective_user.id == game["players"][0].id:
        await update.message.reply_text("تو همین الان سفید هستی 😄")
        return

    game["players"].append(update.effective_user)
    game["status"] = "playing"

    await update.message.reply_text(
        board_text(game) + "\n\n"
        f"⚪ {_mention(game['players'][0])}\n"
        f"⚫ {_mention(game['players'][1])}\n\n"
        "صفحه را لمس کن؛ اول مهره و بعد خانه مقصد را بزن.",
        parse_mode="HTML",
        reply_markup=board_keyboard(game),
    )


# =========================================================
# CALLBACKS
# =========================================================

async def chess6_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""
    parts = data.split(":")
    if not parts or parts[0] != "g6":
        return

    action = parts[1]

    # Cancel
    if action == "x":
        gid = int(parts[2])
        game = CHESS6.get(gid)
        if not game:
            await q.answer("بازی وجود ندارد.", show_alert=True)
            return
        if q.from_user.id != game["players"][0].id:
            await q.answer("فقط سازنده می‌تواند بازی را لغو کند.", show_alert=True)
            return
        CHESS6.pop(gid, None)
        await q.answer()
        await q.edit_message_text("🚪 بازی شطرنج گاتهام لغو شد.")
        return

    gid = int(parts[2])
    game = CHESS6.get(gid)
    if not game:
        await q.answer("این بازی تمام شده.", show_alert=True)
        return

    if action == "r":
        await q.answer()
        await q.edit_message_text(
            board_text(game) + "\n\n" + game_status(game),
            parse_mode="HTML",
            reply_markup=board_keyboard(game),
        )
        return

    if action == "q":
        if q.from_user.id not in [u.id for u in game["players"]]:
            await q.answer("تو بازیکن این بازی نیستی.", show_alert=True)
            return
        winner = game["players"][1] if q.from_user.id == game["players"][0].id else game["players"][0]
        CHESS6.pop(gid, None)
        await q.answer()
        await q.edit_message_text(
            f"🏳️ {_mention(q.from_user)} تسلیم شد.\n\n"
            f"🏆 برنده: {_mention(winner)}",
            parse_mode="HTML",
        )
        return

    if action != "m" or len(parts) != 5:
        return

    if len(game["players"]) < 2:
        await q.answer("هنوز بازیکن دوم وارد نشده.", show_alert=True)
        return

    if q.from_user.id not in [u.id for u in game["players"]]:
        await q.answer("تو بازیکن این بازی نیستی.", show_alert=True)
        return

    white = q.from_user.id == game["players"][0].id
    if white != game["turn"]:
        await q.answer("⏳ نوبت تو نیست!", show_alert=True)
        return

    r, c = int(parts[3]), int(parts[4])
    if not inside(r, c):
        await q.answer("خانه نامعتبر.", show_alert=True)
        return

    # Select a piece
    if game["selected"] is None:
        if not same_side(game["board"][r][c], white):
            await q.answer("اول یکی از مهره‌های خودت رو انتخاب کن.", show_alert=True)
            return
        if not legal_moves_from(game, r, c):
            await q.answer("این مهره فعلاً حرکت قانونی نداره.", show_alert=True)
            return
        game["selected"] = (r, c)
        await q.answer("مقصد رو انتخاب کن ♟️")
        await q.edit_message_text(
            board_text(game) + "\n\n🟢 مقصدهای مجاز را انتخاب کن.",
            parse_mode="HTML",
            reply_markup=board_keyboard(game),
        )
        return

    # Select destination / switch selected piece
    fr, fc = game["selected"]
    if same_side(game["board"][r][c], white):
        if legal_moves_from(game, r, c):
            game["selected"] = (r, c)
            await q.answer("مهره عوض شد.")
            await q.edit_message_reply_markup(reply_markup=board_keyboard(game))
        else:
            await q.answer("این مهره حرکت قانونی ندارد.", show_alert=True)
        return

    legal = legal_moves_from(game, fr, fc)
    if (r, c) not in legal:
        await q.answer("❌ این حرکت قانونی نیست.", show_alert=True)
        return

    before = game["board"][r][c]
    moved_piece = game["board"][fr][fc]

    new_game = apply_move_copy(game, fr, fc, r, c)

    # Capture tracking
    if before != ".":
        if white:
            new_game["captured_black"].append(before)
        else:
            new_game["captured_white"].append(before)

    new_game["moves"].append(f"{rc_to_sq(fr,fc)}-{rc_to_sq(r,c)}")
    new_game["selected"] = None
    game = new_game
    CHESS6[gid] = game

    status = game_status(game)
    moves_left = all_legal_moves(game, game["turn"])

    if not moves_left:
        if in_check(game["board"], game["turn"]):
            winner = game["players"][0] if white else game["players"][1]
            CHESS6.pop(gid, None)
            await q.answer()
            await q.edit_message_text(
                board_text(game) + "\n\n"
                f"🏆 <b>کیش‌ومات!</b>\n"
                f"برنده: {_mention(winner)}",
                parse_mode="HTML",
            )
            return

        CHESS6.pop(gid, None)
        await q.answer()
        await q.edit_message_text(
            board_text(game) + "\n\n🤝 <b>پات — بازی مساوی شد.</b>",
            parse_mode="HTML",
        )
        return

    await q.answer("♟️ حرکت ثبت شد.")
    next_player = game["players"][0] if game["turn"] else game["players"][1]
    await q.edit_message_text(
        board_text(game) + "\n\n"
        f"{status}\n"
        f"👑 نوبت: {_mention(next_player)}",
        parse_mode="HTML",
        reply_markup=board_keyboard(game),
    )


# =========================================================
# REGISTER
# =========================================================

def register_games_pack6(app):
    app.add_handler(CommandHandler("chess6", chess6_cmd))
    app.add_handler(CommandHandler("joinchess6", join_chess6_cmd))
    app.add_handler(
        CallbackQueryHandler(chess6_callback, pattern=r"^g6:")
    )
