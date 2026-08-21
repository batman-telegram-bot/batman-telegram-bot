# -*- coding: utf-8 -*-
"""
card_room.py
================
🃏 Gotham Card Room — اتاق بازی‌های کارتی.

با زدن «پاسور» بازی مستقیم شروع نمی‌شه؛ اول منوی بازی‌های کارتی نمایش داده
می‌شه. بعد از انتخاب بازی، یه لابی با دکمه‌ی «پیوستن» ساخته می‌شه — دقیقاً
مثل بقیه‌ی بازی‌های دونفره‌ی ربات (بیلیارد و ...): سازنده نمی‌تونه رو دکمه‌ی
خودش بزنه، فقط یه نفر دیگه می‌تونه بپیونده و بازی شروع می‌شه.

فعلاً پیاده‌سازی‌شده (کامل و قابل‌بازی):
    🃏 جنگ (War)
    🃏 بیست‌ویک (21 — دو بازیکن مستقل، بدون دیلر)
    🃏 بلک‌جک (در برابر دیلر/ربات، قوانین استاندارد Blackjack)
    🃏 حکم (نسخه‌ی دونفره)

بقیه (هفت‌خبیث، چهاربرگ، پوکر، رامی) فعلاً «به‌زودی» هستن — تو فاز بعدی
اضافه می‌شن؛ دکمه‌شون تو منو هست ولی الان فقط پیام می‌ده.

معماری کارت‌های مخفی:
    چون بازی‌ها تو گروه اجرا می‌شن، دستِ هر بازیکن با دکمه‌ی «🃏 دست من»
    فقط به‌صورت یه popup خصوصی (answer(..., show_alert=True)) به همون بازیکن
    نشون داده می‌شه — این popup توسط تلگرام فقط برای کسی که زده قابل دیدنه،
    پس بازیکن دیگه نمی‌تونه دست حریف رو ببینه. این همون روشیه که group_rps.py
    برای مخفی نگه‌داشتن انتخاب سنگ/کاغذ/قیچی استفاده کرده.
"""

import random
import uuid
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

log = logging.getLogger(__name__)


# =========================================================
#  ابزارهای مشترک: Deck / Shuffle / برچسب کارت
# =========================================================

SUITS = ["♠", "♥", "♦", "♣"]
RED_SUITS = {"♥", "♦"}
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANKS)}  # 2..14 (A=14) برای مقایسه‌ی ساده مثل جنگ/حکم
BJ_VALUE = {**{str(n): n for n in range(2, 11)}, "J": 10, "Q": 10, "K": 10, "A": 11}


def _new_deck():
    deck = [(r, s) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck


def _card_label(card):
    r, s = card
    return f"{r}{s}"


def _hand_label(cards):
    return " ".join(_card_label(c) for c in cards) if cards else "—"


def _gid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _name(user) -> str:
    return user.first_name or user.username or "بازیکن"


def _kw(pattern: str):
    return filters.Regex(rf"(?i)^\s*({pattern})\s*$")


# =========================================================
#  منوی اتاق پاسور
# =========================================================

CARD_ROOM_TEXT = (
    "🃏 *GOTHAM CARD ROOM*\n\n"
    "یه بازی رو انتخاب کن:"
)

CARD_GAMES_MENU = [
    ("hokm", "🃏 حکم"),
    ("haft", "🃏 هفت‌خبیث"),
    ("charbarg", "🃏 چهاربرگ"),
    ("war", "🃏 جنگ"),
    ("bj21", "🃏 بیست‌ویک"),
    ("poker", "🃏 پوکر"),
    ("rummy", "🃏 رامی"),
    ("blackjack", "🃏 بلک‌جک"),
]
CARD_GAME_LABELS = dict(CARD_GAMES_MENU)
IMPLEMENTED_GAMES = {"war", "bj21", "blackjack", "hokm", "haft"}

# بازی‌های چندنفره (۲..۶ نفر) که لابی مخصوص خودشون رو دارن، نه لابی دونفره‌ی cr:join
MULTI_PLAYER_GAMES = {"haft": (2, 6)}

CARD_RULES_TEXT = (
    "📖 *قوانین اتاق پاسور*\n\n"
    "🃏 جنگ — هر بازیکن نصف دسته رو داره؛ هر دور بالاترین کارت رو رو می‌کنه، "
    "برنده هر دو کارت رو می‌بره. تساوی = جنگ (هرکی کارتِ جنگ نداشته باشه می‌بازه).\n\n"
    "🃏 بیست‌ویک — هر بازیکن مستقل Hit/Stand می‌زنه؛ هرکی به ۲۱ نزدیک‌تر باشه بدون "
    "رد شدن، می‌بره.\n\n"
    "🃏 بلک‌جک — در برابر دیلر (ربات)؛ دیلر تا ۱۷ می‌کشه. بلک‌جک (آس+۱۰) برنده‌ی فوریه.\n\n"
    "🃏 حکم (دونفره) — هرکی کارتِ اول بالاتر بیاد حکم (خال برتر) رو انتخاب می‌کنه؛ "
    "هر دست ۱۳ دست کوچیک بازی می‌شه، باید هم‌خال بازی کنی وگرنه می‌تونی حکم بزنی یا "
    "کارت بی‌ربط بندازی؛ هرکی ۷ دست کوچیک رو ببره برنده‌ست.\n\n"
    "🃏 هفت‌خبیث (۲ تا ۶ نفره) — یه کارتِ «خبیث» بی‌جفت تو بازیه. نوبتی از نفر بعدی یه "
    "کارت کور می‌کشی؛ هر جفتِ هم‌ارزش تو دستت رو خودکار دور می‌ندازی. هرکی دستش خالی شد "
    "برنده‌ست و از بازی بیرون میاد؛ آخرین نفری که کارتِ خبیث دستشه می‌بازه. دست هر بازیکن "
    "فقط تو چت خصوصی خودش نشون داده می‌شه.\n\n"
    "چهاربرگ، پوکر و رامی به‌زودی اضافه می‌شن."
)


def _card_room_markup():
    rows, row = [], []
    for key, label in CARD_GAMES_MENU:
        row.append(InlineKeyboardButton(label, callback_data=f"cr:pick:{key}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⚡ بازی سریع", callback_data="cr:quick")])
    rows.append([InlineKeyboardButton("📖 قوانین", callback_data="cr:rules")])
    return InlineKeyboardMarkup(rows)


async def card_room_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        CARD_ROOM_TEXT, reply_markup=_card_room_markup(), parse_mode="Markdown"
    )


# =========================================================
#  لابی مشترک (پیوستن دو نفره) برای همه‌ی بازی‌های کارتی
# =========================================================

CARD_LOBBIES = {}  # token -> {"creator": user, "game": key}


def _lobby_markup(token):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⚔️ پیوستن به بازی", callback_data=f"cr:join:{token}")]])


async def _open_lobby(query_or_msg, creator, game_key, edit=False):
    label = CARD_GAME_LABELS.get(game_key, game_key)
    token = _gid("crlobby")
    CARD_LOBBIES[token] = {"creator": creator, "game": game_key}
    text = (
        f"🃏 GOTHAM CARD ROOM — {label}\n\n"
        f"👤 {_name(creator)} می‌خواد {label} بازی کنه!\n"
        f"⚔️ فقط یه بازیکن دیگه (نه خودِ سازنده) می‌تونه بپیونده."
    )
    if edit:
        await query_or_msg.edit_message_text(text, reply_markup=_lobby_markup(token))
    else:
        await query_or_msg.reply_text(text, reply_markup=_lobby_markup(token))


# =========================================================
#  لابی چندنفره (۲..۶ نفر) — برای بازی‌های کارتی گروهی مثل هفت‌خبیث
# =========================================================

MULTI_LOBBIES = {}  # token -> {"creator": user, "game": key, "players": {uid: user}, "order": [uid,...]}


def _multi_lobby_markup(token, game_key, joined_count):
    min_p, max_p = MULTI_PLAYER_GAMES[game_key]
    rows = [[InlineKeyboardButton("➕ پیوستن", callback_data=f"cr:mjoin:{token}")]]
    row2 = [InlineKeyboardButton("❌ لغو", callback_data=f"cr:mcancel:{token}")]
    if joined_count >= min_p:
        row2.insert(0, InlineKeyboardButton("🚀 شروع بازی", callback_data=f"cr:mstart:{token}"))
    rows.append(row2)
    return InlineKeyboardMarkup(rows)


def _multi_lobby_text(lobby, game_key):
    label = CARD_GAME_LABELS.get(game_key, game_key)
    min_p, max_p = MULTI_PLAYER_GAMES[game_key]
    names = "\n".join(f"👤 {_name(u)}" for u in lobby["order"] and [lobby["players"][uid] for uid in lobby["order"]] or [])
    return (
        f"🃏 GOTHAM CARD ROOM — {label}\n\n"
        f"👥 {len(lobby['order'])}/{max_p} نفر (حداقل {min_p} نفر لازمه)\n\n"
        f"{names}\n\n"
        "با «➕ پیوستن» وارد بازی شو. بعد از رسیدن به حداقل نفرات، سازنده می‌تونه "
        "«🚀 شروع بازی» رو بزنه.\n\n"
        "⚠️ توجه: کارت‌های دستت فقط تو چت خصوصی ربات نشونت داده می‌شه، پس مطمئن شو "
        "قبلاً /start رو تو چت خصوصی ربات زدی."
    )


async def _open_multi_lobby(query_or_msg, creator, game_key, edit=False):
    token = _gid("crmlobby")
    MULTI_LOBBIES[token] = {
        "creator": creator, "game": game_key,
        "players": {creator.id: creator}, "order": [creator.id],
    }
    lobby = MULTI_LOBBIES[token]
    text = _multi_lobby_text(lobby, game_key)
    markup = _multi_lobby_markup(token, game_key, len(lobby["order"]))
    if edit:
        await query_or_msg.edit_message_text(text, reply_markup=markup)
    else:
        await query_or_msg.reply_text(text, reply_markup=markup)


async def _multi_lobby_callback(q, update, context, action, parts):
    token = parts[2]
    lobby = MULTI_LOBBIES.get(token)
    if not lobby:
        await q.answer("این لابی منقضی شده یا بازی شروع شده.", show_alert=True); return
    game_key = lobby["game"]
    min_p, max_p = MULTI_PLAYER_GAMES[game_key]
    user = update.effective_user

    if action == "mcancel":
        if user.id != lobby["creator"].id:
            await q.answer("فقط سازنده‌ی لابی می‌تونه لغوش کنه.", show_alert=True); return
        del MULTI_LOBBIES[token]
        await q.edit_message_text("❌ لابی لغو شد.")
        await q.answer(); return

    if action == "mjoin":
        if user.id in lobby["players"]:
            await q.answer("قبلاً پیوستی.", show_alert=True); return
        if len(lobby["order"]) >= max_p:
            await q.answer("لابی پره.", show_alert=True); return
        lobby["players"][user.id] = user
        lobby["order"].append(user.id)
        await q.edit_message_text(
            _multi_lobby_text(lobby, game_key),
            reply_markup=_multi_lobby_markup(token, game_key, len(lobby["order"])),
        )
        await q.answer("پیوستی! 🃏"); return

    if action == "mstart":
        if user.id != lobby["creator"].id:
            await q.answer("فقط سازنده‌ی لابی می‌تونه بازی رو شروع کنه.", show_alert=True); return
        if len(lobby["order"]) < min_p:
            await q.answer(f"حداقل {min_p} بازیکن لازمه.", show_alert=True); return
        del MULTI_LOBBIES[token]
        players = [lobby["players"][uid] for uid in lobby["order"]]
        await q.answer()
        await MULTI_LAUNCHERS[game_key](context, q.message, players)
        return

    await q.answer()


# =========================================================
#  چت خصوصی برای کارت‌های مخفی — معماری مشترک بازی‌های کارتی چندنفره
# =========================================================
#
# چون تلگرام هیچ راهی برای «نشون دادن یه چیز فقط به یه نفر تو گروه» نداره،
# دستِ هر بازیکن باید تو چت خصوصی (Private Chat) با خودِ ربات فرستاده بشه.
# این بخش سه تا مسئولیت داره:
#   1) فرستادن/آپدیت‌کردن پیامِ دستِ هر بازیکن تو PV خودش (send_or_update_hand)
#   2) اگه بازیکن هنوز /start رو تو PV نزده، به‌جای Crash کردن، پیام گروه رو
#      با راهنما و دکمه‌ی دیپ‌لینک به PV ربات آپدیت می‌کنه و بازی رو مکث می‌کنه
#      (PRIVATE_PENDING) تا وقتی بازیکن /start بزنه.
#   3) وقتی بازیکن /start می‌زنه (با دیپ‌لینک cardhand)، بوت.پی این ماژول رو
#      صدا می‌زنه (try_resume_after_start) تا دستش رو بفرسته و بازی ادامه پیدا کنه.

PRIVATE_PENDING = {}  # user_id -> set of gid هایی که منتظر Start کردنِ این کاربرن


async def _deliver_hand(context, gid, uid, text, markup=None):
    """پیام دستِ بازیکن رو تو PV می‌فرسته یا آپدیت می‌کنه. اگه بازیکن هنوز با ربات
    PV نزده (Forbidden)، uid رو تو PRIVATE_PENDING علامت می‌زنه و False برمی‌گردونه."""
    try:
        await context.bot.send_message(chat_id=uid, text=text, reply_markup=markup)
        PRIVATE_PENDING.setdefault(uid, set()).discard(gid)
        return True
    except Exception as e:
        log.info(f"card_room: could not DM {uid} (probably hasn't started bot): {e}")
        PRIVATE_PENDING.setdefault(uid, set()).add(gid)
        return False


async def _private_hint_markup(context):
    try:
        me = await context.bot.get_me()
        url = f"https://t.me/{me.username}?start=cardhand"
        return InlineKeyboardMarkup([[InlineKeyboardButton("👉 استارت زدن به ربات", url=url)]])
    except Exception:
        return None


async def try_resume_after_start(update, context):
    """از bot.py صدا زده می‌شه وقتی کاربر /start رو با دیپ‌لینک cardhand زده.
    اگه این کاربر تو یه بازی کارتی منتظر Start بوده، الان دستش رو می‌فرستیم و
    اگه همه منتظر بودن، بازی رو ادامه می‌دیم."""
    uid = update.effective_user.id
    pending_gids = list(PRIVATE_PENDING.get(uid, set()))
    if not pending_gids:
        return
    for gid in pending_gids:
        state = HAFT_GAMES.get(gid)
        if not state:
            PRIVATE_PENDING.get(uid, set()).discard(gid)
            continue
        await _haft_resume_player(context, gid, uid)


async def card_room_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    action = parts[1]

    if action == "rules":
        await q.edit_message_text(CARD_RULES_TEXT, reply_markup=_card_room_markup(), parse_mode="Markdown")
        await q.answer(); return

    if action == "quick":
        game_key = random.choice(list(IMPLEMENTED_GAMES))
        await _open_lobby(q.message, update.effective_user, game_key, edit=True)
        await q.answer(f"⚡ {CARD_GAME_LABELS[game_key]} انتخاب شد!"); return

    if action == "pick":
        game_key = parts[2]
        if game_key not in IMPLEMENTED_GAMES:
            await q.answer("این بازی به‌زودی اضافه می‌شه 🚧", show_alert=True); return
        if game_key in MULTI_PLAYER_GAMES:
            await _open_multi_lobby(q.message, update.effective_user, game_key, edit=True)
            await q.answer(); return
        await _open_lobby(q.message, update.effective_user, game_key, edit=True)
        await q.answer(); return

    if action == "join":
        token = parts[2]
        lobby = CARD_LOBBIES.get(token)
        if not lobby:
            await q.answer("این دعوت منقضی شده یا یکی دیگه قبلاً پیوسته.", show_alert=True); return
        creator = lobby["creator"]; joiner = update.effective_user
        if joiner.id == creator.id:
            await q.answer("نمی‌تونی با خودت بازی کنی 🙂", show_alert=True); return
        del CARD_LOBBIES[token]
        game_key = lobby["game"]
        await LAUNCHERS[game_key](q.message, creator, joiner)
        await q.answer(); return

    if action in ("mjoin", "mstart", "mcancel"):
        await _multi_lobby_callback(q, update, context, action, parts)
        return

    await q.answer()


# =========================================================
#  🃏 جنگ (War)
# =========================================================

WAR_GAMES = {}


def _war_text(state, note=""):
    p1, p2 = state["order"]
    n1, n2 = state["names"][p1], state["names"][p2]
    lines = [
        "🃏 GOTHAM WAR",
        f"👤 {n1}: {len(state['piles'][p1])} کارت   |   👤 {n2}: {len(state['piles'][p2])} کارت",
    ]
    if state.get("last"):
        c1, c2 = state["last"]
        lines.append(f"\n{n1}: {_card_label(c1)}      {n2}: {_card_label(c2)}")
    if note:
        lines.append(f"\n{note}")
    return "\n".join(lines)


def _war_markup(gid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎴 دور بعد", callback_data=f"war:go:{gid}")]])


async def _launch_war(target_msg, p1, p2):
    gid = _gid("war")
    deck = _new_deck()
    half = len(deck) // 2
    WAR_GAMES[gid] = {
        "order": [p1.id, p2.id],
        "names": {p1.id: _name(p1), p2.id: _name(p2)},
        "piles": {p1.id: deck[:half], p2.id: deck[half:]},
        "last": None,
    }
    await target_msg.edit_text(_war_text(WAR_GAMES[gid]), reply_markup=_war_markup(gid))


async def war_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    gid = q.data.split(":")[2]
    state = WAR_GAMES.get(gid)
    if not state:
        await q.answer("این بازی تموم شده.", show_alert=True); return
    uid = update.effective_user.id
    p1, p2 = state["order"]
    if uid not in (p1, p2):
        await q.answer("تو تو این بازی نیستی.", show_alert=True); return

    pile = [state["piles"][p1], state["piles"][p2]]
    pot = []

    def _flip_pair():
        c1 = state["piles"][p1].pop(0)
        c2 = state["piles"][p2].pop(0)
        pot.extend([c1, c2])
        return c1, c2

    if not state["piles"][p1] or not state["piles"][p2]:
        loser = p1 if not state["piles"][p1] else p2
        winner = p2 if loser == p1 else p1
        await q.edit_message_text(f"🏆 {state['names'][winner]} برنده‌ی جنگ شد! ({state['names'][loser]} کارت تموم کرد)")
        del WAR_GAMES[gid]; await q.answer(); return

    c1, c2 = _flip_pair()
    note = ""
    while RANK_VALUE[c1[0]] == RANK_VALUE[c2[0]]:
        note += f"⚔️ تساوی ({_card_label(c1)} = {_card_label(c2)}) — جنگ!\n"
        if len(state["piles"][p1]) < 2 or len(state["piles"][p2]) < 2:
            loser = p1 if len(state["piles"][p1]) < 2 else p2
            winner = p2 if loser == p1 else p1
            state["piles"][winner].extend(pot)
            await q.edit_message_text(
                _war_text(state, note + f"🏆 {state['names'][loser]} کارت کافی برای جنگ نداشت. برنده: {state['names'][winner]}")
            )
            del WAR_GAMES[gid]; await q.answer(); return
        # هر بازیکن یه کارت رو (face-down) می‌سوزونه، بعد یکی رو باز می‌کنه
        burn1 = state["piles"][p1].pop(0); burn2 = state["piles"][p2].pop(0)
        pot.extend([burn1, burn2])
        c1, c2 = _flip_pair()

    if RANK_VALUE[c1[0]] > RANK_VALUE[c2[0]]:
        winner = p1
    else:
        winner = p2
    state["piles"][winner].extend(pot)
    state["last"] = (c1, c2)
    note += f"🏆 {state['names'][winner]} این دور رو برد و {len(pot)} کارت گرفت."

    if not state["piles"][p1] or not state["piles"][p2]:
        loser = p1 if not state["piles"][p1] else p2
        champ = p2 if loser == p1 else p1
        await q.edit_message_text(_war_text(state, note + f"\n\n🏆🏆 {state['names'][champ]} کل بازی رو برد!"))
        del WAR_GAMES[gid]; await q.answer(); return

    await q.edit_message_text(_war_text(state, note), reply_markup=_war_markup(gid))
    await q.answer()


# =========================================================
#  🃏 بیست‌ویک (بدون دیلر، دو بازیکن مستقل)
# =========================================================

BJ21_GAMES = {}


def _hand_value_21(cards):
    total = sum(BJ_VALUE[r] for r, _ in cards)
    aces = sum(1 for r, _ in cards if r == "A")
    while total > 21 and aces:
        total -= 10; aces -= 1
    return total


def _bj_text(state, header="🃏 بیست‌ویک گاتهام"):
    lines = [header, ""]
    for uid in state["order"]:
        st = state["status"][uid]
        val = _hand_value_21(state["hands"][uid])
        tag = {"playing": "🎯", "stand": "✋", "bust": "💥"}[st]
        lines.append(f"{tag} {state['names'][uid]}: {_hand_label(state['hands'][uid])}  (مجموع {val})")
    if state["order"] and state["status"][state["order"][state["turn"]]] == "playing":
        lines.append(f"\n🎲 نوبت: {state['names'][state['order'][state['turn']]]}")
    return "\n".join(lines)


def _bj_markup(gid, state, dealer=False):
    if not dealer:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("🃏 Hit", callback_data=f"bj21:hit:{gid}"),
            InlineKeyboardButton("✋ Stand", callback_data=f"bj21:stand:{gid}"),
        ]])
    return None


def _bj_advance_turn(state):
    n = len(state["order"])
    for _ in range(n):
        state["turn"] = (state["turn"] + 1) % n
        if state["status"][state["order"][state["turn"]]] == "playing":
            return True
    return False


def _bj_finish(state):
    lines = ["🏁 پایان بیست‌ویک", ""]
    best_uid, best_val = None, -1
    for uid in state["order"]:
        val = _hand_value_21(state["hands"][uid])
        bust = state["status"][uid] == "bust"
        lines.append(f"👤 {state['names'][uid]}: {_hand_label(state['hands'][uid])} = {val}{' (رد شد 💥)' if bust else ''}")
        if not bust and val > best_val:
            best_val, best_uid = val, uid
    if best_uid:
        lines.append(f"\n🏆 برنده: {state['names'][best_uid]}")
    else:
        lines.append("\n🤝 هر دو رد شدن — بدون برنده.")
    return "\n".join(lines)


async def _launch_bj21(target_msg, p1, p2):
    gid = _gid("bj21")
    deck = _new_deck()
    hands = {p1.id: [deck.pop(), deck.pop()], p2.id: [deck.pop(), deck.pop()]}
    BJ21_GAMES[gid] = {
        "order": [p1.id, p2.id], "names": {p1.id: _name(p1), p2.id: _name(p2)},
        "deck": deck, "hands": hands,
        "status": {p1.id: "playing", p2.id: "playing"}, "turn": 0,
    }
    state = BJ21_GAMES[gid]
    await target_msg.edit_text(_bj_text(state), reply_markup=_bj_markup(gid, state))


async def bj21_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    action, gid = q.data.split(":")[1], q.data.split(":")[2]
    state = BJ21_GAMES.get(gid)
    if not state:
        await q.answer("این بازی تموم شده.", show_alert=True); return
    uid = update.effective_user.id
    if uid not in state["order"]:
        await q.answer("تو تو این بازی نیستی.", show_alert=True); return
    if state["order"][state["turn"]] != uid:
        await q.answer("نوبت تو نیست.", show_alert=True); return

    if action == "hit":
        state["hands"][uid].append(state["deck"].pop())
        if _hand_value_21(state["hands"][uid]) > 21:
            state["status"][uid] = "bust"
            has_more = _bj_advance_turn(state)
            if not has_more:
                await q.edit_message_text(_bj_finish(state)); del BJ21_GAMES[gid]; await q.answer(); return
            await q.edit_message_text(_bj_text(state), reply_markup=_bj_markup(gid, state)); await q.answer(); return
        await q.edit_message_text(_bj_text(state), reply_markup=_bj_markup(gid, state)); await q.answer(); return

    if action == "stand":
        state["status"][uid] = "stand"
        has_more = _bj_advance_turn(state)
        if not has_more:
            await q.edit_message_text(_bj_finish(state)); del BJ21_GAMES[gid]; await q.answer(); return
        await q.edit_message_text(_bj_text(state), reply_markup=_bj_markup(gid, state)); await q.answer(); return


# =========================================================
#  🃏 بلک‌جک (در برابر دیلر/ربات)
# =========================================================

BLACKJACK_GAMES = {}
DEALER_UID = -1


def _bj2_text(state):
    lines = ["🂡 GOTHAM BLACKJACK", ""]
    for uid in state["order"]:
        st = state["status"][uid]
        val = _hand_value_21(state["hands"][uid])
        tag = {"playing": "🎯", "stand": "✋", "bust": "💥", "blackjack": "🂡"}[st]
        lines.append(f"{tag} {state['names'][uid]}: {_hand_label(state['hands'][uid])}  (مجموع {val})")
    dealer_hand = state["dealer"]
    if state["dealer_hidden"]:
        lines.append(f"\n🤖 دیلر: {_card_label(dealer_hand[0])} + 🂠")
    else:
        lines.append(f"\n🤖 دیلر: {_hand_label(dealer_hand)}  (مجموع {_hand_value_21(dealer_hand)})")
    active = [u for u in state["order"] if state["status"][u] == "playing"]
    if active:
        lines.append(f"\n🎲 نوبت: {state['names'][active[0]]}")
    return "\n".join(lines)


def _bj2_markup(gid):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🃏 Hit", callback_data=f"bjd:hit:{gid}"),
        InlineKeyboardButton("✋ Stand", callback_data=f"bjd:stand:{gid}"),
        InlineKeyboardButton("💰 Double", callback_data=f"bjd:double:{gid}"),
    ]])


def _bj2_active_uid(state):
    for u in state["order"]:
        if state["status"][u] == "playing":
            return u
    return None


async def _bj2_run_dealer_and_finish(q, gid, state):
    state["dealer_hidden"] = False
    dealer = state["dealer"]
    while _hand_value_21(dealer) < 17:
        dealer.append(state["deck"].pop())
    dealer_val = _hand_value_21(dealer)
    dealer_bust = dealer_val > 21
    lines = ["🏁 پایان بلک‌جک", "", f"🤖 دیلر: {_hand_label(dealer)} = {dealer_val}{' (رد شد 💥)' if dealer_bust else ''}", ""]
    for uid in state["order"]:
        pval = _hand_value_21(state["hands"][uid])
        st = state["status"][uid]
        if st == "bust":
            result = "باخت 💥"
        elif st == "blackjack" and dealer_val == 21 and len(dealer) == 2:
            result = "مساوی (هر دو بلک‌جک) 🤝"
        elif st == "blackjack":
            result = "بلک‌جک! برد 🏆"
        elif dealer_bust:
            result = "برد (دیلر رد شد) 🏆"
        elif pval > dealer_val:
            result = "برد 🏆"
        elif pval == dealer_val:
            result = "مساوی 🤝"
        else:
            result = "باخت 💥"
        lines.append(f"👤 {state['names'][uid]}: {_hand_label(state['hands'][uid])} = {pval} → {result}")
    await q.edit_message_text("\n".join(lines))
    del BLACKJACK_GAMES[gid]


async def _launch_blackjack(target_msg, p1, p2):
    gid = _gid("bjd")
    deck = _new_deck()
    hands = {p1.id: [deck.pop(), deck.pop()], p2.id: [deck.pop(), deck.pop()]}
    dealer = [deck.pop(), deck.pop()]
    status = {}
    for uid, u in ((p1.id, p1), (p2.id, p2)):
        status[uid] = "blackjack" if _hand_value_21(hands[uid]) == 21 else "playing"
    BLACKJACK_GAMES[gid] = {
        "order": [p1.id, p2.id], "names": {p1.id: _name(p1), p2.id: _name(p2)},
        "deck": deck, "hands": hands, "status": status,
        "dealer": dealer, "dealer_hidden": True, "doubled": set(),
    }
    state = BLACKJACK_GAMES[gid]
    if _bj2_active_uid(state) is None:
        class _Fake:  # فقط برای امضای تابع لازم نیست چون q اینجا موجود نیست
            pass
    await target_msg.edit_text(_bj2_text(state), reply_markup=_bj2_markup(gid) if _bj2_active_uid(state) else None)
    if _bj2_active_uid(state) is None:
        # هر دو همون اول بلک‌جک زدن؛ مستقیم دیلر بازی می‌کنه
        state["dealer_hidden"] = False
        dealer_val = _hand_value_21(dealer)
        while dealer_val < 17:
            dealer.append(deck.pop()); dealer_val = _hand_value_21(dealer)
        lines = ["🏁 پایان بلک‌جک", "", f"🤖 دیلر: {_hand_label(dealer)} = {dealer_val}", ""]
        for uid in state["order"]:
            res = "مساوی (هر دو بلک‌جک) 🤝" if dealer_val == 21 and len(dealer) == 2 else "بلک‌جک! برد 🏆"
            lines.append(f"👤 {state['names'][uid]}: {_hand_label(hands[uid])} → {res}")
        await target_msg.edit_text("\n".join(lines))
        del BLACKJACK_GAMES[gid]


async def blackjack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    action, gid = q.data.split(":")[1], q.data.split(":")[2]
    state = BLACKJACK_GAMES.get(gid)
    if not state:
        await q.answer("این بازی تموم شده.", show_alert=True); return
    uid = update.effective_user.id
    if uid not in state["order"]:
        await q.answer("تو تو این بازی نیستی.", show_alert=True); return
    active = _bj2_active_uid(state)
    if active != uid:
        await q.answer("نوبت تو نیست.", show_alert=True); return

    if action == "hit":
        state["hands"][uid].append(state["deck"].pop())
        if _hand_value_21(state["hands"][uid]) > 21:
            state["status"][uid] = "bust"
        nxt = _bj2_active_uid(state)
        if nxt is None:
            await _bj2_run_dealer_and_finish(q, gid, state); await q.answer(); return
        await q.edit_message_text(_bj2_text(state), reply_markup=_bj2_markup(gid)); await q.answer(); return

    if action == "stand":
        state["status"][uid] = "stand"
        nxt = _bj2_active_uid(state)
        if nxt is None:
            await _bj2_run_dealer_and_finish(q, gid, state); await q.answer(); return
        await q.edit_message_text(_bj2_text(state), reply_markup=_bj2_markup(gid)); await q.answer(); return

    if action == "double":
        if len(state["hands"][uid]) != 2 or uid in state["doubled"]:
            await q.answer("Double فقط با دو کارت اول ممکنه.", show_alert=True); return
        state["doubled"].add(uid)
        state["hands"][uid].append(state["deck"].pop())
        if _hand_value_21(state["hands"][uid]) > 21:
            state["status"][uid] = "bust"
        else:
            state["status"][uid] = "stand"
        nxt = _bj2_active_uid(state)
        if nxt is None:
            await _bj2_run_dealer_and_finish(q, gid, state); await q.answer(); return
        await q.edit_message_text(_bj2_text(state), reply_markup=_bj2_markup(gid)); await q.answer(); return


# =========================================================
#  🃏 حکم — نسخه‌ی دونفره
# =========================================================

HOKM_GAMES = {}
HOKM_TRICKS_TO_WIN = 7


def _hokm_deal_full(deck):
    return deck[:13], deck[13:26]


def _hokm_text(state):
    p1, p2 = state["order"]
    lines = ["🃏 GOTHAM HOKM (دونفره)", ""]
    if state["phase"] == "choose_trump":
        lines.append(f"🂠 حکم‌بند: {state['names'][state['hakem']]}")
        lines.append("منتظر انتخاب خالِ حکم...")
        return "\n".join(lines)
    lines.append(f"👑 خالِ حکم: {state['trump']}")
    lines.append(f"🏆 دست‌ها: {state['names'][p1]} {state['tricks'][p1]} — {state['tricks'][p2]} {state['names'][p2]}")
    if state["table"]:
        who, card = state["table"][0]
        lines.append(f"\n🎯 روی زمین: {state['names'][who]} → {_card_label(card)}")
    else:
        lines.append("\n🎯 زمین خالیه.")
    turn_uid = state["order"][state["turn"]]
    lines.append(f"🎲 نوبت: {state['names'][turn_uid]}")
    return "\n".join(lines)


def _hokm_hand_markup(gid, hand):
    rows, row = [], []
    for i, c in enumerate(hand):
        row.append(InlineKeyboardButton(_card_label(c), callback_data=f"hokm:play:{gid}:{i}"))
        if len(row) == 4:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows) if rows else None


def _hokm_trump_markup(gid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(s, callback_data=f"hokm:trump:{gid}:{s}") for s in SUITS]])


def _hokm_control_markup(gid, state):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🃏 دست من (خصوصی)", callback_data=f"hokm:hand:{gid}")]])


async def _launch_hokm(target_msg, p1, p2):
    gid = _gid("hokm")
    deck = _new_deck()
    # یه کارت به هر بازیکن برای تعیین حکم‌بند
    c1, c2 = deck.pop(), deck.pop()
    while RANK_VALUE[c1[0]] == RANK_VALUE[c2[0]]:
        deck.append(c1); deck.append(c2); random.shuffle(deck)
        c1, c2 = deck.pop(), deck.pop()
    hakem = p1.id if RANK_VALUE[c1[0]] > RANK_VALUE[c2[0]] else p2.id
    deck = _new_deck()
    h1, h2 = _hokm_deal_full(deck)
    h1.sort(key=lambda c: (c[1], RANK_VALUE[c[0]]))
    h2.sort(key=lambda c: (c[1], RANK_VALUE[c[0]]))
    HOKM_GAMES[gid] = {
        "order": [p1.id, p2.id], "names": {p1.id: _name(p1), p2.id: _name(p2)},
        "hands": {p1.id: h1, p2.id: h2},
        "hakem": hakem, "trump": None, "phase": "choose_trump",
        "tricks": {p1.id: 0, p2.id: 0}, "table": [], "turn": 0,
    }
    state = HOKM_GAMES[gid]
    if hakem == p2.id:
        state["order"] = [p2.id, p1.id]
    await target_msg.edit_text(_hokm_text(state), reply_markup=_hokm_trump_markup(gid))


def _hokm_start_play(state):
    state["phase"] = "play"
    hakem_idx = state["order"].index(state["hakem"])
    state["turn"] = hakem_idx


def _hokm_valid_indices(hand, table, trump):
    if not table:
        return list(range(len(hand)))
    lead_suit = table[0][1][1]
    same = [i for i, c in enumerate(hand) if c[1] == lead_suit]
    return same if same else list(range(len(hand)))


def _hokm_resolve_trick(state):
    (u1, c1), (u2, c2) = state["table"]
    trump = state["trump"]
    lead_suit = c1[1]
    if c1[1] == c2[1]:
        winner = u1 if RANK_VALUE[c1[0]] > RANK_VALUE[c2[0]] else u2
    elif c1[1] == trump:
        winner = u1
    elif c2[1] == trump:
        winner = u2
    else:
        winner = u1  # هیچ‌کدوم هم‌خالِ لید یا حکم نیست جز اولی؛ اولی می‌بره چون رنگ رو داشته
    state["tricks"][winner] += 1
    state["table"] = []
    state["turn"] = state["order"].index(winner)
    return winner


async def hokm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    action, gid = parts[1], parts[2]
    state = HOKM_GAMES.get(gid)
    if not state:
        await q.answer("این بازی تموم شده.", show_alert=True); return
    uid = update.effective_user.id
    if uid not in state["order"]:
        await q.answer("تو تو این بازی نیستی.", show_alert=True); return

    if action == "trump":
        if uid != state["hakem"]:
            await q.answer("فقط حکم‌بند خالِ حکم رو انتخاب می‌کنه.", show_alert=True); return
        state["trump"] = parts[3]
        _hokm_start_play(state)
        await q.edit_message_text(_hokm_text(state), reply_markup=_hokm_control_markup(gid, state))
        await q.answer(f"حکم: {state['trump']}"); return

    if action == "hand":
        hand = state["hands"][uid]
        if state["phase"] != "play" or state["order"][state["turn"]] != uid:
            await q.answer(f"دست تو: {_hand_label(hand)}", show_alert=True); return
        valid = _hokm_valid_indices(hand, state["table"], state["trump"])
        text = "🃏 دست تو (بزن تا بازی کنی):\n" + "\n".join(
            f"{i+1}. {_card_label(c)}{'  ✅' if i in valid else ''}" for i, c in enumerate(hand)
        )
        await q.answer(text[:200], show_alert=True)
        # کیبورد واقعی برای بازی‌کردن، زیر همون پیام گروه (فقط دکمه‌ها، بدون افشای کارت رقیب)
        try:
            await q.edit_message_reply_markup(reply_markup=_hokm_hand_markup(gid, hand))
        except Exception:
            pass
        return

    if action == "play":
        if state["phase"] != "play":
            await q.answer("هنوز حکم انتخاب نشده.", show_alert=True); return
        if state["order"][state["turn"]] != uid:
            await q.answer("نوبت تو نیست.", show_alert=True); return
        idx = int(parts[3])
        hand = state["hands"][uid]
        if idx >= len(hand):
            await q.answer("این کارت دیگه دستت نیست.", show_alert=True); return
        valid = _hokm_valid_indices(hand, state["table"], state["trump"])
        if idx not in valid:
            await q.answer("باید هم‌خالِ زمین بازی کنی (اگه داری).", show_alert=True); return
        card = hand.pop(idx)
        state["table"].append((uid, card))

        if len(state["table"]) == 1:
            other = [p for p in state["order"] if p != uid][0]
            state["turn"] = state["order"].index(other)
            await q.edit_message_text(_hokm_text(state), reply_markup=_hokm_control_markup(gid, state))
            await q.answer(f"کارتِ {_card_label(card)} بازی شد."); return

        winner = _hokm_resolve_trick(state)
        note = f"🎯 دست کوچیک رو {state['names'][winner]} برد."
        if state["tricks"][winner] >= HOKM_TRICKS_TO_WIN:
            loser = [p for p in state["order"] if p != winner][0]
            await q.edit_message_text(
                f"{_hokm_text(state)}\n\n{note}\n\n🏆🏆 {state['names'][winner]} با {state['tricks'][winner]} دست برنده‌ی بازی شد!"
            )
            del HOKM_GAMES[gid]; await q.answer(); return

        if not state["hands"][state["order"][0]] and not state["hands"][state["order"][1]]:
            p1, p2 = state["order"]
            champ = p1 if state["tricks"][p1] > state["tricks"][p2] else p2
            await q.edit_message_text(
                f"{_hokm_text(state)}\n\n{note}\n\n🏁 کارت‌ها تموم شد. 🏆 برنده: {state['names'][champ]}"
            )
            del HOKM_GAMES[gid]; await q.answer(); return

        await q.edit_message_text(_hokm_text(state) + f"\n\n{note}", reply_markup=_hokm_control_markup(gid, state))
        await q.answer(); return


# =========================================================
#  🃏 هفت‌خبیث (Old-Maid style, ۲..۶ نفره) — با چت خصوصی
# =========================================================

HAFT_GAMES = {}          # gid -> state
HAFT_REMATCH = {}        # token -> [PseudoUser, ...]
HAFT_VILLAIN = ("Q", "♠")
HAFT_TURN_TIMEOUT_SEC = 90


class _PseudoUser:
    """برای دکمه‌ی «بازی مجدد» — بعد از تموم‌شدن بازی، آبجکت User واقعی تلگرام رو
    نداریم، پس یه نسخه‌ی سبک نگه می‌داریم که _name() باهاش کار کنه."""
    def __init__(self, uid, first_name, username=""):
        self.id = uid
        self.first_name = first_name
        self.username = username


def _haft_new_deck():
    deck = [(r, s) for s in SUITS for r in RANKS]
    # فقط بی‌بی‌پیک رو نگه می‌داریم؛ سه‌تای دیگه حذف می‌شن تا این کارت تو کل بازی جفت نداشته باشه
    deck = [c for c in deck if not (c[0] == "Q" and c[1] != "♠")]
    return deck  # ۴۹ کارت؛ (Q,♠) تنها کارتِ «خبیث»ه


def _haft_discard_pairs(hand):
    """جفت‌های هم‌ارزش (صرف‌نظر از خال) رو از دست حذف می‌کنه؛ کارتِ خبیث هیچ‌وقت جفت نداره
    چون تو کل بازی فقط یه دونه‌ست. لیستِ کارت‌های حذف‌شده رو برمی‌گردونه."""
    removed = []
    ranks = {}
    for c in hand:
        ranks.setdefault(c[0], []).append(c)
    for rank, cards in ranks.items():
        pairs = len(cards) // 2
        for c in cards[: pairs * 2]:
            hand.remove(c)
            removed.append(c)
    return removed


def _haft_job_name(gid):
    return f"haft_timeout_{gid}"


def _haft_cancel_job(app, gid):
    if not getattr(app, "job_queue", None):
        return
    for job in app.job_queue.get_jobs_by_name(_haft_job_name(gid)):
        job.schedule_removal()


def _haft_schedule_timeout(app, gid):
    _haft_cancel_job(app, gid)
    if getattr(app, "job_queue", None):
        app.job_queue.run_once(_haft_turn_timeout, when=HAFT_TURN_TIMEOUT_SEC,
                                data={"gid": gid}, name=_haft_job_name(gid))


def _haft_text(state, note=""):
    lines = ["🃏 GOTHAM — هفت‌خبیث", ""]
    for uid in state["order"]:
        mark = "👉 " if state["order"][state["turn_idx"]] == uid else "• "
        lines.append(f"{mark}{state['names'][uid]}: {len(state['hands'][uid])} کارت")
    if state["out_order"]:
        winners = "، ".join(state["names"][u] for u in state["out_order"])
        lines.append(f"\n✅ دستشون خالی شده (تو بازی نیستن): {winners}")
    if note:
        lines.append(f"\n{note}")
    lines.append(f"\n⏳ نوبتِ {state['names'][state['order'][state['turn_idx']]]}")
    return "\n".join(lines)


def _haft_markup(gid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎴 کشیدن کارت", callback_data=f"haft:draw:{gid}")],
        [InlineKeyboardButton("🃏 دست من", callback_data=f"haft:hand:{gid}"),
         InlineKeyboardButton("🏳 خروج از بازی", callback_data=f"haft:leave:{gid}")],
    ])


def _haft_end_markup(token):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔁 بازی مجدد", callback_data=f"haft:rematch:{token}")]])


async def _haft_send_hand(context, gid, uid):
    state = HAFT_GAMES.get(gid)
    if not state or uid not in state["hands"]:
        return
    hand = state["hands"][uid]
    text = (
        f"🃏 دستِ تو تو بازیِ هفت‌خبیث:\n\n{_hand_label(hand)}\n\n"
        f"({len(hand)} کارت) — برای دیدن وضعیتِ کلی به گروه برگرد."
    )
    ok = await _deliver_hand(context, gid, uid, text)
    if not ok:
        hint = await _private_hint_markup(context)
        try:
            await context.bot.send_message(
                chat_id=state["chat_id"],
                text=(f"⚠️ {state['names'][uid]} هنوز چت خصوصی با ربات رو Start نکرده؛ "
                      "برای دیدن کارت‌هاش باید اول تو PV ربات /start بزنه، بعد بازی ادامه پیدا می‌کنه."),
                reply_markup=hint,
            )
        except Exception:
            pass
    return ok


async def _haft_resume_player(context, gid, uid):
    """وقتی کاربر تو PV ربات /start می‌زنه، صدا زده می‌شه: دستِ فعلیش رو می‌فرسته."""
    ok = await _haft_send_hand(context, gid, uid)
    state = HAFT_GAMES.get(gid)
    if ok and state:
        PRIVATE_PENDING.get(uid, set()).discard(gid)
        try:
            await context.bot.send_message(
                chat_id=state["chat_id"],
                text=f"✅ {state['names'][uid]} وارد چت خصوصی ربات شد؛ بازی ادامه پیدا می‌کنه.",
            )
        except Exception:
            pass


async def _launch_haft(context, target_msg, players):
    gid = _gid("haft")
    deck = _haft_new_deck()
    random.shuffle(deck)
    hands = {u.id: [] for u in players}
    for i, c in enumerate(deck):
        hands[players[i % len(players)].id].append(c)
    for uid in hands:
        _haft_discard_pairs(hands[uid])

    order = [u.id for u in players if len(hands[u.id]) > 0]
    names = {u.id: _name(u) for u in players}
    state = {
        "chat_id": target_msg.chat_id, "message_id": None,
        "order": order, "names": names, "hands": hands,
        "out_order": [u.id for u in players if len(hands[u.id]) == 0],
        "turn_idx": 0, "processing": False,
        "player_objs": players,
    }
    HAFT_GAMES[gid] = state

    if len(order) <= 1:
        # اتفاق نادر: بعد از تقسیم اولیه، بقیه دستشون کاملاً جفت شده و خالی شده
        await _haft_finish(context, gid, target_msg, note="🍀 شانسی! همون تقسیمِ اول همه‌چی رو جفت کرد.")
        return

    msg = await target_msg.edit_text(_haft_text(state), reply_markup=_haft_markup(gid))
    state["message_id"] = msg.message_id
    _haft_schedule_timeout(context.application, gid)
    for uid in order:
        await _haft_send_hand(context, gid, uid)


async def _haft_finish(context, gid, message=None, note=""):
    state = HAFT_GAMES.get(gid)
    if not state:
        return
    _haft_cancel_job(context.application, gid)
    loser = state["order"][0] if state["order"] else None
    winner = state["out_order"][0] if state["out_order"] else None
    if loser and winner:
        try:
            import bot as _bot
            _bot._record_game_result(state["chat_id"], winner, loser)
        except Exception as e:
            log.info(f"haft: could not save game record (harmless): {e}")
    text = "🃏 بازی هفت‌خبیث تموم شد."
    if note:
        text = f"{note}\n\n{text}"
    if loser:
        text += f"\n\n💀 {state['names'][loser]} کارتِ خبیث دستش موند و باخت!"
        if winner:
            text += f"\n🏆 برنده: {state['names'][winner]}"
    token = _gid("haftrm")
    HAFT_REMATCH[token] = state["player_objs"]
    markup = _haft_end_markup(token)
    try:
        if message is not None:
            await message.edit_text(text, reply_markup=markup)
        elif state.get("message_id"):
            await context.bot.edit_message_text(
                chat_id=state["chat_id"], message_id=state["message_id"],
                text=text, reply_markup=markup,
            )
        else:
            await context.bot.send_message(chat_id=state["chat_id"], text=text, reply_markup=markup)
    except Exception as e:
        log.info(f"haft: finish edit failed (harmless): {e}")
    del HAFT_GAMES[gid]


async def _haft_execute_turn(context, gid, acting_uid, auto=False):
    state = HAFT_GAMES.get(gid)
    if not state or state.get("processing"):
        return
    state["processing"] = True
    try:
        order = state["order"]
        if acting_uid not in order:
            return
        cur_idx = order.index(acting_uid)
        nxt_idx = (cur_idx + 1) % len(order)
        nxt_uid = order[nxt_idx]
        cur_hand = state["hands"][acting_uid]
        nxt_hand = state["hands"][nxt_uid]
        if not nxt_hand:
            return
        draw_idx = random.randrange(len(nxt_hand))
        card = nxt_hand.pop(draw_idx)
        cur_hand.append(card)
        removed_pairs = _haft_discard_pairs(cur_hand)

        note = f"🎴 {state['names'][acting_uid]} از {state['names'][nxt_uid]} یه کارت کور کشید."
        if auto:
            note = f"⏱️ زمان تموم شد — {note}"
        if removed_pairs:
            note += f"\n🃏 {state['names'][acting_uid]} یه جفت دور انداخت."

        finishing = []
        if not nxt_hand:
            finishing.append(nxt_uid)
        if not cur_hand:
            finishing.append(acting_uid)
        for uid in finishing:
            if uid in state["order"]:
                state["order"].remove(uid)
                state["out_order"].append(uid)

        try:
            bot_app = context.application
        except Exception:
            bot_app = None

        if len(state["order"]) <= 1:
            await _haft_finish(context, gid, message=None, note=note)
            return

        # نوبت رو به نفر بعدیِ فعال بده
        if acting_uid in state["order"]:
            state["turn_idx"] = state["order"].index(acting_uid)
            state["turn_idx"] = (state["turn_idx"] + 1) % len(state["order"])
        else:
            state["turn_idx"] = state["turn_idx"] % len(state["order"])

        try:
            await context.bot.edit_message_text(
                chat_id=state["chat_id"], message_id=state["message_id"],
                text=_haft_text(state, note=note), reply_markup=_haft_markup(gid),
            )
        except Exception as e:
            log.info(f"haft: edit failed (harmless): {e}")

        if bot_app:
            _haft_schedule_timeout(bot_app, gid)

        for uid in {acting_uid, nxt_uid} & set(state["order"]):
            await _haft_send_hand(context, gid, uid)
    finally:
        state["processing"] = False


async def _haft_turn_timeout(context: ContextTypes.DEFAULT_TYPE):
    gid = context.job.data["gid"]
    state = HAFT_GAMES.get(gid)
    if not state:
        return
    uid = state["order"][state["turn_idx"]]
    await _haft_execute_turn(context, gid, uid, auto=True)


async def haft_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    action = parts[1]
    token_or_gid = parts[2]

    if action == "rematch":
        players = HAFT_REMATCH.pop(token_or_gid, None)
        if not players:
            await q.answer("این دکمه دیگه معتبر نیست.", show_alert=True); return
        await q.answer("🃏 بازی مجدد شروع شد!")
        await _launch_haft(context, q.message, players)
        return

    gid = token_or_gid
    state = HAFT_GAMES.get(gid)
    if not state:
        await q.answer("این بازی تموم شده یا پیدا نشد.", show_alert=True); return
    uid = update.effective_user.id

    if action == "hand":
        if uid not in state["hands"] or uid not in state["order"]:
            await q.answer("تو تو این بازی نیستی یا کارت‌هات تموم شده.", show_alert=True); return
        await q.answer("🃏 دستت رو تو PV فرستادم.")
        await _haft_send_hand(context, gid, uid)
        return

    if action == "leave":
        if uid not in state["order"]:
            await q.answer("تو تو این بازی نیستی.", show_alert=True); return
        _haft_cancel_job(context.application, gid)
        state["order"].remove(uid)
        remaining = state["order"]
        if remaining:
            winner = min(remaining, key=lambda x: len(state["hands"][x]))
            try:
                import bot as _bot
                _bot._record_game_result(state["chat_id"], winner, uid)
            except Exception as e:
                log.info(f"haft: could not save forfeit record (harmless): {e}")
            text = (f"🏳 {state['names'][uid]} از هفت‌خبیث انصراف داد؛ بازی همین‌جا تموم شد.\n"
                    f"🏆 برنده: {state['names'][winner]}")
        else:
            text = f"🏳 {state['names'][uid]} از هفت‌خبیث انصراف داد. بازی تموم شد."
        token = _gid("haftrm")
        HAFT_REMATCH[token] = state["player_objs"]
        try:
            await q.edit_message_text(text, reply_markup=_haft_end_markup(token))
        except Exception:
            pass
        del HAFT_GAMES[gid]
        await q.answer(); return

    if action == "draw":
        if state.get("processing"):
            await q.answer("یه لحظه صبر کن، دور قبلی داره پردازش می‌شه...", show_alert=True); return
        if uid not in state["order"]:
            await q.answer("تو تو این بازی نیستی یا بردی/از بازی خارج شدی.", show_alert=True); return
        if state["order"][state["turn_idx"]] != uid:
            await q.answer("الان نوبتِ تو نیست.", show_alert=True); return
        await q.answer()
        await _haft_execute_turn(context, gid, uid)
        return

    await q.answer()


MULTI_LAUNCHERS = {
    "haft": _launch_haft,
}


# =========================================================
#  راه‌انداز هر بازی (از لابی مشترک صدا زده می‌شه)
# =========================================================

LAUNCHERS = {
    "war": _launch_war,
    "bj21": _launch_bj21,
    "blackjack": _launch_blackjack,
    "hokm": _launch_hokm,
}


# =========================================================
#  ثبت هندلرها
# =========================================================

def register_card_room(app):
    app.add_handler(MessageHandler(_kw("پاسور|کارت|بازی پاسور|بازی کارت"), card_room_start), group=12)
    app.add_handler(CallbackQueryHandler(card_room_callback, pattern=r"^cr:"), group=5)
    app.add_handler(CallbackQueryHandler(war_callback, pattern=r"^war:"), group=5)
    app.add_handler(CallbackQueryHandler(bj21_callback, pattern=r"^bj21:"), group=5)
    app.add_handler(CallbackQueryHandler(blackjack_callback, pattern=r"^bjd:"), group=5)
    app.add_handler(CallbackQueryHandler(hokm_callback, pattern=r"^hokm:"), group=5)
    app.add_handler(CallbackQueryHandler(haft_callback, pattern=r"^haft:"), group=5)
