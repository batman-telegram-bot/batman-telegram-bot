# -*- coding: utf-8 -*-
"""
games_pack5.py
================
۴ بازی جدید، هم‌خانواده با بقیه‌ی فایل‌های games*.py (کلمه‌محرک، بدون /،
دکمه‌های شیشه‌ای).

بازی‌ها:
    ۱. یونو (UNO)      -> کلمه: "یونو"           (۲ تا ۴ نفره، دکمه‌ی پیوستن)
    ۲. قلمرو           -> کلمه: "قلمرو"           (۲ تا ۴ نفره، دکمه‌ی پیوستن)
    ۳. بیلیارد          -> کلمه: "بیلیارد"          (دو نفره، ریپلای یا دکمه‌ی پیوستن)
    ۴. مسابقه ماشین    -> کلمه: "مسابقه ماشین"    (۲ تا ۴ نفره، دکمه‌ی پیوستن)

نکته: چون تلگرام گرافیک/فیزیک بلادرنگ نداره، بیلیارد و مسابقه ماشین نسخه‌ی
نوبتی و ساده‌شده‌ان (نه فیزیک واقعی)، ولی کاملاً قابل‌بازی و بدون باگ‌ان.
یونو الان یه تایمر ۴۵ ثانیه‌ای نوبت هم داره: اگه بازیکن/انتخاب‌کننده‌ی رنگ
دیر کنه، خودکار یه کارت می‌کشه (یا رنگ رندوم انتخاب می‌شه) و نوبت رد می‌شه —
تا بازی گروه رو قفل نکنه. چون پیام‌ها تو گروه عمومیه، دست بازیکن‌ها (مثل
بقیه‌ی بازی‌های این ربات) فقط موقع نوبتشون رو دکمه‌ها دیده می‌شه.

نحوه‌ی اتصال (کنار بقیه‌ی register_ها تو bot.py):

    from games_pack5 import register_extra_games3

    register_extra_games3(app)     # <-- این خط رو اضافه کن
"""

import random
import uuid
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters

log = logging.getLogger(__name__)


EXTRA_GAMES_LIST_TEXT5 = (
    "یونو — ۲ تا ۴ نفره، دکمه‌ی «پیوستن» رو بزن\n"
    "قلمرو — ۲ تا ۴ نفره، استراتژیک: منابع/نیرو/دفاع/حمله/توسعه، ۱۰ دور، بیشترین امتیاز می‌بره\n"
    "بیلیارد — دو نفره، ریپلای کن یا «پیوستن» رو بزن، توپ‌ها رو بزن و آخرش ۸ سیاه\n"
    "مسابقه ماشین — ۲ تا ۴ نفره، تاس بنداز، بوست و لکه‌روغن رو مدیریت کن\n"
)


def _kw5(text: str):
    return filters.Regex(rf"(?i)^\s*{text}\s*$")


def _gid5(prefix: str) -> str:
    return prefix + uuid.uuid4().hex[:8]


def _name5(user) -> str:
    return user.first_name or user.username or "بازیکن"


def _join_markup5(prefix: str, gid: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ پیوستن", callback_data=f"{prefix}:join:{gid}")],
        [InlineKeyboardButton("🚀 شروع بازی", callback_data=f"{prefix}:beg:{gid}"),
         InlineKeyboardButton("❌ لغو", callback_data=f"{prefix}:cancel:{gid}")],
    ])


async def _noop5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


# =========================================================
#  ۱. یونو (UNO) — ۲ تا ۴ نفره
# =========================================================

UNO_GAMES = {}
UNO_COLORS = {"R": "🔴", "G": "🟢", "B": "🔵", "Y": "🟡"}
UNO_LABELS = {"skip": "⏭", "reverse": "🔄", "+2": "+2"}
UNO_TURN_TIMEOUT_SEC = 45


def _uno_build_deck():
    deck = []
    for c in "RGBY":
        deck.append((c, "0"))
        for v in list("123456789") + ["skip", "reverse", "+2"]:
            deck.append((c, v))
            deck.append((c, v))
    for _ in range(4):
        deck.append(("W", "wild"))
        deck.append(("W", "+4"))
    random.shuffle(deck)
    return deck


def _uno_card_label(card):
    c, v = card
    if c == "W":
        return "🃏W" if v == "wild" else "🃏+4"
    return f"{UNO_COLORS[c]}{UNO_LABELS.get(v, v)}"


def _uno_draw(game, n=1):
    cards = []
    for _ in range(n):
        if not game["deck"]:
            top = game["discard"][-1]
            rest = game["discard"][:-1]
            if not rest:
                break
            random.shuffle(rest)
            game["deck"] = rest
            game["discard"] = [top]
        if game["deck"]:
            cards.append(game["deck"].pop())
    return cards


def _uno_advance(game, effect):
    n = len(game["players"])
    if effect == "reverse":
        if n == 2:
            return  # تو دونفره، ریورس مثل اسکیپه: نوبت همون بازیکنه
        game["direction"] *= -1
        game["turn"] = (game["turn"] + game["direction"]) % n
        return
    next_idx = (game["turn"] + game["direction"]) % n
    if effect == "skip":
        game["turn"] = (next_idx + game["direction"]) % n
    elif effect == "draw2":
        game["hands"][game["players"][next_idx]].extend(_uno_draw(game, 2))
        game["turn"] = (next_idx + game["direction"]) % n
    elif effect == "draw4":
        game["hands"][game["players"][next_idx]].extend(_uno_draw(game, 4))
        game["turn"] = (next_idx + game["direction"]) % n
    else:
        game["turn"] = next_idx


def _uno_job_name(gid):
    return f"uno_turn:{gid}"


def _uno_cancel_timer(app, gid):
    for job in app.job_queue.get_jobs_by_name(_uno_job_name(gid)):
        job.schedule_removal()


def _uno_schedule_timer(app, gid, game, chat_id, message_id):
    """تایمر ۴۵ ثانیه‌ای نوبت. با «timer_token» چک می‌کنیم که تایمر قدیمی
    (که قبل از رسیدنش، نوبت با یه اکشن دیگه عوض شده) اثری نداشته باشه، حتی
    اگه schedule_removal به هر دلیلی جا مونده باشه."""
    _uno_cancel_timer(app, gid)
    game["timer_token"] = game.get("timer_token", 0) + 1
    app.job_queue.run_once(
        _uno_turn_timeout,
        when=UNO_TURN_TIMEOUT_SEC,
        data={"gid": gid, "token": game["timer_token"], "chat_id": chat_id, "message_id": message_id},
        name=_uno_job_name(gid),
    )


async def _uno_turn_timeout(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    gid = d["gid"]
    game = UNO_GAMES.get(gid)
    if not game or game.get("timer_token") != d["token"]:
        return  # بازی تموم شده یا این تایمر قدیمیه و نوبت عوض شده
    try:
        if game.get("awaiting"):
            uid = game["awaiting"]["uid"]
            name = game["names"][uid]
            color = random.choice("RGBY")
            card = game["awaiting"]["card"]
            game["color"] = color; game["value"] = card[1]
            effect = "draw4" if card[1] == "+4" else "normal"
            game["awaiting"] = None
            _uno_advance(game, effect)
            note = f"\n\n⏱️ {name} تو انتخاب رنگ دیر کرد — رنگ {UNO_COLORS[color]} خودکار انتخاب شد."
        else:
            uid = game["players"][game["turn"]]
            name = game["names"][uid]
            game["hands"][uid].extend(_uno_draw(game, 1))
            _uno_advance(game, "normal")
            note = f"\n\n⏱️ {name} تو نوبتش دیر کرد — یه کارت خودکار کشید و نوبت رد شد."
        _uno_schedule_timer(context.application, gid, game, d["chat_id"], d["message_id"])
        await context.bot.edit_message_text(
            chat_id=d["chat_id"], message_id=d["message_id"],
            text=_uno_text(game) + note, reply_markup=_uno_markup(gid, game),
        )
    except Exception as e:
        log.info(f"uno turn-timeout handling failed (harmless): {e}")


def _uno_text(game):
    lines = ["🃏 یونو گاتهام", ""]
    top = game["discard"][-1]
    lines.append(f"روی زمین: {_uno_card_label(top)}   (رنگ جاری: {UNO_COLORS.get(game['color'], '🃏')})")
    lines.append("")
    for uid in game["players"]:
        marker = "👉 " if game["players"][game["turn"]] == uid else "   "
        lines.append(f"{marker}{game['names'][uid]}: {len(game['hands'][uid])} کارت")
    if game.get("awaiting"):
        lines.append(f"\n🎨 {game['names'][game['awaiting']['uid']]} باید رنگ انتخاب کنه...")
    else:
        lines.append(f"\n🎯 نوبت: {game['names'][game['players'][game['turn']]]}")
    return "\n".join(lines)


def _uno_markup(gid, game):
    if not game["started"]:
        return _join_markup5("uno", gid)
    if game.get("awaiting"):
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(UNO_COLORS[c], callback_data=f"uno:color:{gid}:{c}") for c in "RGBY"
        ]])
    uid = game["players"][game["turn"]]
    hand = game["hands"][uid]
    rows, row = [], []
    for i, card in enumerate(hand):
        row.append(InlineKeyboardButton(_uno_card_label(card), callback_data=f"uno:play:{gid}:{i}"))
        if len(row) == 4:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("🃏 کشیدن کارت", callback_data=f"uno:draw:{gid}")])
    return InlineKeyboardMarkup(rows)


async def uno_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    gid = _gid5("un")
    UNO_GAMES[gid] = {
        "chat_id": update.effective_chat.id, "players": [uid],
        "names": {uid: _name5(update.effective_user)}, "started": False,
        "timer_token": 0,
    }
    await update.effective_message.reply_text(
        f"🃏 یونو گاتهام\n\n👤 {_name5(update.effective_user)}\n۲ تا ۴ نفر می‌تونن وارد بشن.",
        reply_markup=_join_markup5("uno", gid),
    )


async def uno_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    action, gid = parts[1], parts[2]
    game = UNO_GAMES.get(gid)
    if not game:
        await q.answer("این بازی تمام شده.", show_alert=True)
        return
    uid = update.effective_user.id

    if action == "join":
        if uid in game["players"]:
            await q.answer("قبلاً وارد شدی.", show_alert=True); return
        if game["started"] or len(game["players"]) >= 4:
            await q.answer("ورود ممکن نیست.", show_alert=True); return
        game["players"].append(uid); game["names"][uid] = _name5(update.effective_user)
        names_txt = "\n".join(f"👤 {game['names'][p]}" for p in game["players"])
        await q.edit_message_text(f"🃏 یونو گاتهام\n\n{names_txt}\n\n۲ تا ۴ نفر.", reply_markup=_join_markup5("uno", gid))
        await q.answer(); return

    if action == "beg":
        if uid != game["players"][0] or len(game["players"]) < 2:
            await q.answer("حداقل ۲ نفر لازمه و فقط سازنده شروع می‌کنه.", show_alert=True); return
        deck = _uno_build_deck()
        hands = {p: [deck.pop() for _ in range(7)] for p in game["players"]}
        first = deck.pop()
        color = first[0] if first[0] != "W" else random.choice("RGBY")
        game.update({
            "started": True, "deck": deck, "discard": [first], "hands": hands,
            "color": color, "value": first[1], "turn": 0, "direction": 1, "awaiting": None,
        })
        await q.edit_message_text(_uno_text(game), reply_markup=_uno_markup(gid, game))
        _uno_schedule_timer(context.application, gid, game, game["chat_id"], q.message.message_id)
        await q.answer(); return

    if action == "cancel":
        if uid == game["players"][0]:
            _uno_cancel_timer(context.application, gid)
            del UNO_GAMES[gid]
            await q.edit_message_text("🃏 یونو لغو شد.")
        await q.answer(); return

    if not game["started"]:
        await q.answer(); return

    if game.get("awaiting"):
        if action == "color":
            if uid != game["awaiting"]["uid"]:
                await q.answer("نوبت انتخاب رنگ تو نیست.", show_alert=True); return
            color = parts[3]
            card = game["awaiting"]["card"]
            game["color"] = color; game["value"] = card[1]
            effect = "draw4" if card[1] == "+4" else "normal"
            game["awaiting"] = None
            _uno_advance(game, effect)
            await q.edit_message_text(_uno_text(game), reply_markup=_uno_markup(gid, game))
            _uno_schedule_timer(context.application, gid, game, game["chat_id"], q.message.message_id)
        await q.answer(); return

    if uid != game["players"][game["turn"]]:
        await q.answer("نوبت تو نیست.", show_alert=True); return

    if action == "play":
        idx = int(parts[3])
        hand = game["hands"][uid]
        if idx < 0 or idx >= len(hand):
            await q.answer("این کارت وجود نداره.", show_alert=True); return
        card = hand[idx]
        valid = card[0] == "W" or card[0] == game["color"] or card[1] == game["value"]
        if not valid:
            await q.answer("این کارت با رنگ/عدد روی زمین جور نیست.", show_alert=True); return
        hand.pop(idx)
        game["discard"].append(card)
        if not hand:
            _uno_cancel_timer(context.application, gid)
            await q.edit_message_text(f"🃏 یونو تمام شد!\n\n🏆 برنده: {game['names'][uid]}\n🎉 کارت‌هاش تموم شد!")
            del UNO_GAMES[gid]; await q.answer(); return
        if card[0] == "W":
            game["awaiting"] = {"uid": uid, "card": card}
            await q.edit_message_text(_uno_text(game), reply_markup=_uno_markup(gid, game))
            _uno_schedule_timer(context.application, gid, game, game["chat_id"], q.message.message_id)
            await q.answer(); return
        game["color"] = card[0]; game["value"] = card[1]
        effect = {"skip": "skip", "reverse": "reverse", "+2": "draw2"}.get(card[1], "normal")
        _uno_advance(game, effect)
        await q.edit_message_text(_uno_text(game), reply_markup=_uno_markup(gid, game))
        _uno_schedule_timer(context.application, gid, game, game["chat_id"], q.message.message_id)
        await q.answer(); return

    if action == "draw":
        game["hands"][uid].extend(_uno_draw(game, 1))
        _uno_advance(game, "normal")
        await q.edit_message_text(_uno_text(game), reply_markup=_uno_markup(gid, game))
        _uno_schedule_timer(context.application, gid, game, game["chat_id"], q.message.message_id)
        await q.answer(); return


# =========================================================
#  ۲. قلمرو (Kingdom) — استراتژیک، ۲ تا ۴ نفره
#     هر بازیکن: قلمرو با منابع/نیرو/دفاع/سطح/امتیاز؛ هر نوبت یکی از ۶ اقدام
#     رو انتخاب می‌کنه: حمله، دفاع، جمع‌آوری منابع، توسعه‌ی قلمرو، ارتقا،
#     یا یه اقدام استراتژیک (کمک به یه هم‌پیمان). بعد از TER_MAX_ROUNDS دور
#     کامل، بازیکنی که بیشترین امتیاز رو داره برنده‌ست.
# =========================================================

TER_GAMES = {}
TER_COLORS = ["🔴", "🟢", "🟡", "🔵"]
TER_MAX_ROUNDS = 10
TER_TURN_TIMEOUT_SEC = 45

TER_ACTIONS = {
    "gather": ("💰 جمع‌آوری منابع", 0),
    "build": ("🏰 توسعه قلمرو", None),   # هزینه‌ش به سطح فعلی بستگی داره
    "upgrade": ("🔬 ارتقا", 25),
    "defend": ("🛡 دفاع", 15),
    "attack": ("⚔️ حمله", 0),
    "alliance": ("🤝 اقدام استراتژیک", 10),
}


def _ter_new_kingdom():
    return {"resources": 40, "power": 10, "defense": 10, "level": 1, "score": 0}


def _ter_score(k):
    return k["level"] * 100 + k["resources"] + k["power"] * 5 + k["defense"] * 2


def _ter_build_cost(level):
    return 30 + level * 15


def _ter_text(game):
    lines = ["🏰 GOTHAM KINGDOM — نبرد قلمروها", ""]
    if not game["started"]:
        for uid in game["players"]:
            lines.append(f"👤 {game['names'][uid]}")
        lines.append("\n۲ تا ۴ نفر می‌تونن وارد بشن.")
        return "\n".join(lines)
    for i, uid in enumerate(game["players"]):
        k = game["kingdoms"][uid]
        marker = "👉 " if game["players"][game["turn"]] == uid else "   "
        lines.append(
            f"{marker}{TER_COLORS[i % 4]} {game['names'][uid]} — سطح {k['level']} | "
            f"💰{k['resources']} ⚔️{k['power']} 🛡{k['defense']} | امتیاز: {_ter_score(k)}"
        )
    lines.append(f"\n🗓 دور {game['round']} از {TER_MAX_ROUNDS}")
    if game.get("log"):
        lines.append(f"\n📜 {game['log']}")
    lines.append(f"\n🎯 نوبت: {game['names'][game['players'][game['turn']]]}")
    return "\n".join(lines)


def _ter_markup(gid, game):
    if not game["started"]:
        return _join_markup5("ter", gid)
    uid = game["players"][game["turn"]]
    level = game["kingdoms"][uid]["level"]
    build_label = f"🏰 توسعه قلمرو (ۀ{_ter_build_cost(level)}💰)"
    rows = [
        [InlineKeyboardButton("⚔️ حمله", callback_data=f"ter:attack:{gid}"),
         InlineKeyboardButton("🛡 دفاع (۱۵💰)", callback_data=f"ter:defend:{gid}")],
        [InlineKeyboardButton("💰 جمع‌آوری منابع", callback_data=f"ter:gather:{gid}")],
        [InlineKeyboardButton(build_label, callback_data=f"ter:build:{gid}")],
        [InlineKeyboardButton("🔬 ارتقا (۲۵💰)", callback_data=f"ter:upgrade:{gid}"),
         InlineKeyboardButton("🤝 استراتژیک (۱۰💰)", callback_data=f"ter:alliance:{gid}")],
        [InlineKeyboardButton("🏳️ خروج", callback_data=f"ter:leave:{gid}")],
    ]
    return InlineKeyboardMarkup(rows)


def _ter_target_markup(gid, game, action):
    uid = game["players"][game["turn"]]
    rows = []
    for p in game["players"]:
        if p == uid:
            continue
        rows.append([InlineKeyboardButton(f"🎯 {game['names'][p]}", callback_data=f"ter:{action}t:{gid}:{p}")])
    rows.append([InlineKeyboardButton("🔙 انصراف", callback_data=f"ter:cancelaction:{gid}")])
    return InlineKeyboardMarkup(rows)


async def territory_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    gid = _gid5("te")
    TER_GAMES[gid] = {
        "chat_id": update.effective_chat.id, "players": [uid],
        "names": {uid: _name5(update.effective_user)}, "turn": 0, "started": False,
        "round": 1, "log": "", "timer_token": 0,
    }
    await update.effective_message.reply_text(
        _ter_text(TER_GAMES[gid]), reply_markup=_join_markup5("ter", gid),
    )


def _ter_job_name(gid):
    return f"ter_turn:{gid}"


def _ter_cancel_timer(app, gid):
    for job in app.job_queue.get_jobs_by_name(_ter_job_name(gid)):
        job.schedule_removal()


def _ter_schedule_timer(app, gid, game, chat_id, message_id):
    _ter_cancel_timer(app, gid)
    game["timer_token"] = game.get("timer_token", 0) + 1
    app.job_queue.run_once(
        _ter_turn_timeout, when=TER_TURN_TIMEOUT_SEC,
        data={"gid": gid, "token": game["timer_token"], "chat_id": chat_id, "message_id": message_id},
        name=_ter_job_name(gid),
    )


async def _ter_turn_timeout(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    gid = d["gid"]
    game = TER_GAMES.get(gid)
    if not game or game.get("timer_token") != d["token"]:
        return
    try:
        uid = game["players"][game["turn"]]
        name = game["names"][uid]
        game["log"] = f"⏱️ {name} تو نوبتش دیر کرد و نوبتش رد شد (بدون اقدام)."
        _ter_end_turn(game)
        _ter_schedule_timer(context.application, gid, game, d["chat_id"], d["message_id"])
        finished = _ter_maybe_finish(gid, game)
        if finished:
            await context.bot.edit_message_text(chat_id=d["chat_id"], message_id=d["message_id"], text=finished)
            _ter_cancel_timer(context.application, gid)
            return
        await context.bot.edit_message_text(
            chat_id=d["chat_id"], message_id=d["message_id"],
            text=_ter_text(game), reply_markup=_ter_markup(gid, game),
        )
    except Exception as e:
        log.info(f"territory turn-timeout handling failed (harmless): {e}")


def _ter_end_turn(game):
    """نوبت رو می‌بره جلو؛ اگه یه دور کامل شد، شمارنده‌ی دور رو زیاد می‌کنه."""
    game["turn"] += 1
    if game["turn"] >= len(game["players"]):
        game["turn"] = 0
        game["round"] += 1


def _ter_maybe_finish(gid, game):
    """اگه دورها تموم شده باشه، متن نتیجه‌ی نهایی رو برمی‌گردونه و بازی رو پاک می‌کنه؛
    وگرنه None."""
    if game["round"] <= TER_MAX_ROUNDS:
        return None
    scored = sorted(game["players"], key=lambda p: _ter_score(game["kingdoms"][p]), reverse=True)
    lines = ["🏰 نبرد قلمروها تمام شد!", ""]
    for i, p in enumerate(scored, 1):
        k = game["kingdoms"][p]
        medal = "🏆" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "▫️"))
        lines.append(f"{medal} {game['names'][p]} — سطح {k['level']} | امتیاز {_ter_score(k)}")
    del TER_GAMES[gid]
    return "\n".join(lines)


async def territory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    action, gid = parts[1], parts[2]
    game = TER_GAMES.get(gid)
    if not game:
        await q.answer("این بازی تمام شده.", show_alert=True); return
    uid = update.effective_user.id

    if action == "join":
        if uid in game["players"]:
            await q.answer("قبلاً وارد شدی.", show_alert=True); return
        if game["started"] or len(game["players"]) >= 4:
            await q.answer("ورود ممکن نیست.", show_alert=True); return
        game["players"].append(uid); game["names"][uid] = _name5(update.effective_user)
        await q.edit_message_text(_ter_text(game), reply_markup=_join_markup5("ter", gid))
        await q.answer(); return

    if action == "beg":
        if uid != game["players"][0] or len(game["players"]) < 2:
            await q.answer("حداقل ۲ نفر لازمه و فقط سازنده شروع می‌کنه.", show_alert=True); return
        game["started"] = True
        game["kingdoms"] = {p: _ter_new_kingdom() for p in game["players"]}
        await q.edit_message_text(_ter_text(game), reply_markup=_ter_markup(gid, game))
        _ter_schedule_timer(context.application, gid, game, game["chat_id"], q.message.message_id)
        await q.answer(); return

    if action == "cancel":
        if uid == game["players"][0]:
            del TER_GAMES[gid]
            await q.edit_message_text("🏰 قلمرو لغو شد.")
        await q.answer(); return

    if not game["started"]:
        await q.answer(); return

    if action == "leave":
        if len(game["players"]) <= 2:
            _ter_cancel_timer(context.application, gid)
            del TER_GAMES[gid]
            await q.edit_message_text("🏰 بازی قلمرو پایان یافت.")
            await q.answer(); return
        if uid in game["players"]:
            game["players"].remove(uid); game["names"].pop(uid, None); game["kingdoms"].pop(uid, None)
            game["turn"] %= len(game["players"])
            await q.edit_message_text(_ter_text(game), reply_markup=_ter_markup(gid, game))
        await q.answer(); return

    if action == "cancelaction":
        if uid != game["players"][game["turn"]]:
            await q.answer(); return
        await q.edit_message_text(_ter_text(game), reply_markup=_ter_markup(gid, game))
        await q.answer(); return

    # اقدام‌های هدف‌دار (حمله / کمک استراتژیک) دو مرحله‌این: اول نفر رو انتخاب کن
    if action in ("attack", "alliance") and uid == game["players"][game["turn"]] and len(parts) == 3:
        if len(game["players"]) == 2:
            target = next(p for p in game["players"] if p != uid)
            action = action + "t"
            parts = [parts[0], action, gid, str(target)]
        else:
            await q.edit_message_text(
                f"{_ter_text(game)}\n\n🎯 هدفت رو انتخاب کن:", reply_markup=_ter_target_markup(gid, game, action)
            )
            await q.answer(); return

    if uid != game["players"][game["turn"]]:
        await q.answer("نوبت تو نیست.", show_alert=True); return

    k = game["kingdoms"][uid]

    if action == "gather":
        gained = random.randint(8, 15) + k["level"] * 2
        k["resources"] += gained
        game["log"] = f"💰 {game['names'][uid]} {gained} منبع جمع کرد."
        _ter_end_turn(game)

    elif action == "build":
        cost = _ter_build_cost(k["level"])
        if k["resources"] < cost:
            await q.answer(f"منابع کافی نیست (نیاز: {cost}💰).", show_alert=True); return
        k["resources"] -= cost
        k["level"] += 1
        k["defense"] += 5
        game["log"] = f"🏰 {game['names'][uid]} قلمروش رو به سطح {k['level']} رسوند."
        _ter_end_turn(game)

    elif action == "upgrade":
        if k["resources"] < 25:
            await q.answer("منابع کافی نیست (نیاز: ۲۵💰).", show_alert=True); return
        k["resources"] -= 25
        k["power"] += 8
        game["log"] = f"🔬 {game['names'][uid]} نیروی نظامیش رو ارتقا داد."
        _ter_end_turn(game)

    elif action == "defend":
        if k["resources"] < 15:
            await q.answer("منابع کافی نیست (نیاز: ۱۵💰).", show_alert=True); return
        k["resources"] -= 15
        k["defense"] += 10
        game["log"] = f"🛡 {game['names'][uid]} دفاع قلمروش رو تقویت کرد."
        _ter_end_turn(game)

    elif action == "attackt":
        target = int(parts[3])
        tk = game["kingdoms"][target]
        if k["power"] > tk["defense"]:
            loot = max(5, int(tk["resources"] * random.uniform(0.2, 0.4)))
            tk["resources"] = max(0, tk["resources"] - loot)
            tk["defense"] = max(0, tk["defense"] - 5)
            k["resources"] += loot
            game["log"] = f"⚔️ {game['names'][uid]} به {game['names'][target]} حمله کرد و برد! (+{loot}💰 غنیمت)"
        else:
            k["power"] = max(0, k["power"] - 5)
            game["log"] = f"⚔️ حمله‌ی {game['names'][uid]} به {game['names'][target]} شکست خورد (دفاع حریف قوی‌تر بود)."
        _ter_end_turn(game)

    elif action == "alliancet":
        target = int(parts[3])
        if k["resources"] < 10:
            await q.answer("منابع کافی نیست (نیاز: ۱۰💰).", show_alert=True); return
        k["resources"] -= 10
        game["kingdoms"][target]["resources"] += 15
        game["log"] = f"🤝 {game['names'][uid]} به {game['names'][target]} کمک استراتژیک کرد (+۱۵💰 براش)."
        _ter_end_turn(game)

    else:
        await q.answer(); return

    _ter_schedule_timer(context.application, gid, game, game["chat_id"], q.message.message_id)
    finished = _ter_maybe_finish(gid, game)
    if finished:
        _ter_cancel_timer(context.application, gid)
        await q.edit_message_text(finished)
        await q.answer(); return
    await q.edit_message_text(_ter_text(game), reply_markup=_ter_markup(gid, game))
    await q.answer()


# =========================================================
#  ۳. بیلیارد (ساده‌شده) — دو نفره
# =========================================================

BIL_GAMES = {}
BIL_LOBBIES = {}


def _bil_lobby_markup(token):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🙋 بپیوند به بازی", callback_data=f"lobby5:{token}")]])


def _bil_markup(gid, state):
    balls = sorted(state["remaining"]) if state["remaining"] else [8]
    rows, row = [], []
    for n in balls:
        label = "⚫ ۸" if n == 8 else f"🎱 {n}"
        row.append(InlineKeyboardButton(label, callback_data=f"bil:hit:{gid}:{n}"))
        if len(row) == 4:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


async def _launch_billiards(target_msg, p1, p2, edit=False):
    gid = f"{target_msg.chat.id}_{p1.id}_{p2.id}_{random.randint(1000,9999)}"
    BIL_GAMES[gid] = {
        "players": {p1.id: 0, p2.id: 0},
        "names": {p1.id: p1.first_name, p2.id: p2.first_name},
        "remaining": set(range(1, 8)), "turn": p1.id,
    }
    text = (
        f"🎱 بیلیارد: {p1.first_name} در برابر {p2.first_name}\n"
        f"۷ توپ رو زمینه، آخرش باید ۸ سیاه رو بندازی (اگه زودتر بزنیش می‌بازی).\n\n"
        f"🎯 نوبت: {p1.first_name}"
    )
    markup = _bil_markup(gid, BIL_GAMES[gid])
    if edit:
        await target_msg.edit_text(text, reply_markup=markup)
    else:
        await target_msg.reply_text(text, reply_markup=markup)


async def billiards_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    creator = update.effective_user
    if msg.reply_to_message and msg.reply_to_message.from_user and \
       not msg.reply_to_message.from_user.is_bot and msg.reply_to_message.from_user.id != creator.id:
        await _launch_billiards(msg, creator, msg.reply_to_message.from_user)
        return
    token = f"{update.effective_chat.id}_{creator.id}_{random.randint(100000, 999999)}"
    BIL_LOBBIES[token] = {"creator": creator, "kind": "bil"}
    await msg.reply_text(
        f"🎮 {creator.first_name} می‌خواد بیلیارد بازی کنه!\nحریف، دکمه‌ی زیر رو بزن تا بازی شروع بشه.",
        reply_markup=_bil_lobby_markup(token),
    )


async def bil_lobby_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    token = query.data.split(":", 1)[1]
    lobby = BIL_LOBBIES.get(token)
    if not lobby:
        await query.answer("این دعوت منقضی شده یا یکی دیگه قبلاً پیوسته.", show_alert=True); return
    creator = lobby["creator"]; joiner = query.from_user
    if joiner.id == creator.id:
        await query.answer("نمی‌تونی با خودت بازی کنی 🙂", show_alert=True); return
    del BIL_LOBBIES[token]
    await _launch_billiards(query.message, creator, joiner, edit=True)
    await query.answer()


async def billiards_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    gid, n = parts[2], int(parts[3])
    state = BIL_GAMES.get(gid)
    if not state:
        await q.answer("این بازی تموم شده.", show_alert=True); return
    uid = update.effective_user.id
    if uid not in state["players"]:
        await q.answer("تو تو این بازی نیستی.", show_alert=True); return
    if state["turn"] != uid:
        await q.answer("نوبت تو نیست.", show_alert=True); return
    other = [p for p in state["players"] if p != uid][0]

    if n == 8:
        if state["remaining"]:
            await q.edit_message_text(f"⚫ {state['names'][uid]} زودتر از موقع ۸ سیاه رو زد! باخت.\n🏆 برنده: {state['names'][other]}")
            del BIL_GAMES[gid]; await q.answer(); return
        if random.random() < 0.6:
            await q.edit_message_text(f"⚫🎉 {state['names'][uid]} ۸ سیاه رو زد و برد!\n🏆 برنده: {state['names'][uid]}")
            del BIL_GAMES[gid]; await q.answer(); return
        state["turn"] = other
        await q.edit_message_text(f"😅 {state['names'][uid]} به ۸ نزد.\n🎯 نوبت: {state['names'][other]}", reply_markup=_bil_markup(gid, state))
        await q.answer(); return

    if n not in state["remaining"]:
        await q.answer("این توپ قبلاً رفته.", show_alert=True); return

    if random.random() < 0.65:
        state["remaining"].discard(n)
        state["players"][uid] += 1
        text = f"🎱 {state['names'][uid]} توپ {n} رو زد! ({state['players'][uid]} امتیاز)\n🎯 نوبت: {state['names'][uid]} (ادامه)"
        if not state["remaining"]:
            text += "\n\n⚫ حالا باید ۸ سیاه رو بزنی!"
        await q.edit_message_text(text, reply_markup=_bil_markup(gid, state))
        await q.answer(); return
    else:
        state["turn"] = other
        await q.edit_message_text(f"❌ {state['names'][uid]} به توپ {n} نخورد.\n🎯 نوبت: {state['names'][other]}", reply_markup=_bil_markup(gid, state))
        await q.answer(); return


# =========================================================
#  ۴. مسابقه ماشین — ۲ تا ۴ نفره، تاسی، بوست/لکه‌روغن
# =========================================================

RACE_GAMES = {}
RACE_LEN = 30
RACE_ICONS = ["🚗", "🚙", "🚕", "🏎️"]
RACE_BOOST = {5: 3, 12: 4, 22: 3}
RACE_OIL = {8: -3, 17: -4, 25: -2}


def _race_text(game):
    lines = [
        "🏁 مسابقه ماشین گاتهام", "",
        "🟢 بوست تو متر: " + "، ".join(str(k) for k in RACE_BOOST),
        "🛢️ لکه‌روغن تو متر: " + "، ".join(str(k) for k in RACE_OIL), "",
    ]
    for i, uid in enumerate(game["players"]):
        marker = "👉 " if game["started"] and game["players"][game["turn"]] == uid else "   "
        pos = max(0, min(game["pos"][uid], RACE_LEN))
        lines.append(f"{marker}{RACE_ICONS[i % 4]} {game['names'][uid]}: متر {pos}/{RACE_LEN}")
    if game["started"]:
        lines.append(f"\n🎯 نوبت: {game['names'][game['players'][game['turn']]]}")
    return "\n".join(lines)


def _race_markup(gid, game):
    if not game["started"]:
        return _join_markup5("race", gid)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 گاز بده!", callback_data=f"race:go:{gid}")],
        [InlineKeyboardButton("🏳️ خروج", callback_data=f"race:leave:{gid}")],
    ])


async def racing_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    gid = _gid5("rc")
    RACE_GAMES[gid] = {
        "chat_id": update.effective_chat.id, "players": [uid],
        "names": {uid: _name5(update.effective_user)}, "pos": {uid: 0}, "turn": 0, "started": False,
    }
    await update.effective_message.reply_text(
        f"🏁 مسابقه ماشین گاتهام\n\n👤 {_name5(update.effective_user)}\n۲ تا ۴ نفر می‌تونن وارد بشن.",
        reply_markup=_join_markup5("race", gid),
    )


async def racing_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    action, gid = parts[1], parts[2]
    game = RACE_GAMES.get(gid)
    if not game:
        await q.answer("این بازی تمام شده.", show_alert=True); return
    uid = update.effective_user.id

    if action == "join":
        if uid in game["players"]:
            await q.answer("قبلاً وارد شدی.", show_alert=True); return
        if game["started"] or len(game["players"]) >= 4:
            await q.answer("ورود ممکن نیست.", show_alert=True); return
        game["players"].append(uid); game["names"][uid] = _name5(update.effective_user); game["pos"][uid] = 0
        await q.edit_message_text(_race_text(game), reply_markup=_join_markup5("race", gid))
        await q.answer(); return

    if action == "beg":
        if uid != game["players"][0] or len(game["players"]) < 2:
            await q.answer("حداقل ۲ نفر لازمه و فقط سازنده شروع می‌کنه.", show_alert=True); return
        game["started"] = True
        await q.edit_message_text(_race_text(game), reply_markup=_race_markup(gid, game))
        await q.answer(); return

    if action == "cancel":
        if uid == game["players"][0]:
            del RACE_GAMES[gid]
            await q.edit_message_text("🏁 مسابقه لغو شد.")
        await q.answer(); return

    if not game["started"]:
        await q.answer(); return

    if action == "leave":
        if len(game["players"]) <= 2:
            del RACE_GAMES[gid]
            await q.edit_message_text("🏁 مسابقه پایان یافت.")
            await q.answer(); return
        game["players"].remove(uid); game["names"].pop(uid, None); game["pos"].pop(uid, None)
        game["turn"] %= len(game["players"])
        await q.edit_message_text(_race_text(game), reply_markup=_race_markup(gid, game))
        await q.answer(); return

    if uid != game["players"][game["turn"]]:
        await q.answer("نوبت تو نیست.", show_alert=True); return

    if action == "go":
        roll = random.randint(1, 6)
        old = game["pos"][uid]
        new = old + roll
        extra = ""
        if new >= RACE_LEN:
            await q.edit_message_text(
                f"🏁 {game['names'][uid]} با تاس {roll} خط پایان رو رد کرد!\n\n🏆 برنده: {game['names'][uid]}"
            )
            del RACE_GAMES[gid]; await q.answer(); return
        if new in RACE_BOOST:
            new += RACE_BOOST[new]; extra = " 🟢 بوست گرفتی!"
        elif new in RACE_OIL:
            new = max(0, new + RACE_OIL[new]); extra = " 🛢️ رو روغن سر خوردی!"
        if new >= RACE_LEN:
            await q.edit_message_text(
                f"🏁 {game['names'][uid]} با تاس {roll}{extra} خط پایان رو رد کرد!\n\n🏆 برنده: {game['names'][uid]}"
            )
            del RACE_GAMES[gid]; await q.answer(); return
        game["pos"][uid] = new
        game["turn"] = (game["turn"] + 1) % len(game["players"])
        await q.edit_message_text(
            _race_text(game) + f"\n\n🎲 {game['names'][uid]} تاس {roll} آورد: {old} → {new}.{extra}",
            reply_markup=_race_markup(gid, game),
        )
        await q.answer(); return


# =========================================================
#  ثبت هندلرها
# =========================================================

def register_extra_games3(app):
    # نکته: MessageHandler های زیر نباید group=5 بگیرن، چون count_message تو
    # games_pack3.py یه MessageHandler(filters.TEXT & ~filters.COMMAND) با
    # group=5 داره که رو هر متنی match می‌شه و اگه زودتر ثبت بشه، جلوی این‌ها رو
    # می‌گیره. برای همین گروه اختصاصی ۱۲ استفاده شده.
    app.add_handler(MessageHandler(_kw5("یونو|بازی یونو|uno"), uno_start), group=12)
    app.add_handler(CallbackQueryHandler(uno_callback, pattern=r"^uno:"), group=5)

    app.add_handler(MessageHandler(_kw5("قلمرو|بازی قلمرو"), territory_start), group=12)
    app.add_handler(CallbackQueryHandler(territory_callback, pattern=r"^ter:"), group=5)

    app.add_handler(MessageHandler(_kw5("بیلیارد|بازی بیلیارد"), billiards_start), group=12)
    app.add_handler(CallbackQueryHandler(billiards_callback, pattern=r"^bil:"), group=5)
    app.add_handler(CallbackQueryHandler(bil_lobby_join_callback, pattern=r"^lobby5:"), group=5)

    app.add_handler(MessageHandler(_kw5("مسابقه ماشین|بازی مسابقه ماشین|مسابقه"), racing_start), group=12)
    app.add_handler(CallbackQueryHandler(racing_callback, pattern=r"^race:"), group=5)

    app.add_handler(CallbackQueryHandler(_noop5, pattern=r"^noop5$"), group=5)
