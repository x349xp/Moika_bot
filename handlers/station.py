import time

from aiogram import Router, F
from aiogram.types import CallbackQuery

import db
import config
import keyboards as kb

router = Router()


def status_ru(status: str) -> str:
    return {"free": "свободен 🟢", "busy": "занят 🟡", "broken": "сломан 🔴"}.get(status, status)


def worker_status_ru(w) -> str:
    if w["status"] == "idle":
        return "простаивает 🟢"
    left = max(0, int(w["busy_until"] - time.time()))
    m, s = divmod(left, 60)
    return f"работает 🟡 (~{m}м{s}с)"


@router.callback_query(F.data == "menu:station")
async def cb_station(callback: CallbackQuery):
    conn = await db.get_conn()
    try:
        user = await db.get_user(conn, callback.from_user.id)
        bays = await db.get_bays(conn, callback.from_user.id)
        workers = await db.get_workers(conn, callback.from_user.id)
        queue = await db.get_queue(conn, callback.from_user.id)
    finally:
        await conn.close()

    since_last = round(user["balance"] - user["last_seen_balance"], 1)
    lines = [
        "🏢 <b>Обзор мойки</b>",
        f"💰 Баланс: {round(user['balance'],1)}💰" + (f"  (с прошлого визита: +{since_last}💰)" if since_last > 0 else ""),
        f"⭐ Репутация: {round(user['reputation'],1)}",
        "",
        f"🚪 Боксы ({len(bays)}):",
    ]
    for b in bays:
        lines.append(f"  #{b['bay_id']} — {status_ru(b['status'])}")

    lines.append("")
    lines.append(f"👷 Мойщики ({len(workers)}):")
    for w in workers:
        wl = config.WORKER_LEVELS[w["level"]]
        lines.append(f"  {wl['name']} — {worker_status_ru(w)}")

    lines.append("")
    lines.append(f"📋 В очереди: {len(queue)}/{config.MAX_QUEUE_SIZE}")

    conn = await db.get_conn()
    try:
        await conn.execute(
            "UPDATE users SET last_seen_balance=? WHERE user_id=?", (user["balance"], callback.from_user.id)
        )
        await conn.commit()
    finally:
        await conn.close()

    await callback.message.edit_text("\n".join(lines), reply_markup=kb.back_to_menu(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "menu:workers")
async def cb_workers(callback: CallbackQuery):
    conn = await db.get_conn()
    try:
        workers = await db.get_workers(conn, callback.from_user.id)
    finally:
        await conn.close()

    lines = ["👷 <b>Твои мойщики</b>", ""]
    if not workers:
        lines.append("Пока никого нет — загляни в меню найма.")
    for w in workers:
        wl = config.WORKER_LEVELS[w["level"]]
        lines.append(
            f"• {wl['name']} — скорость ×{wl['speed']}, качество {int(wl['quality']*100)}% — {worker_status_ru(w)}"
        )
    lines.append("")
    lines.append("Нанять нового мойщика:")

    kb_builder = kb.hire_menu()
    await callback.message.edit_text("\n".join(lines), reply_markup=kb_builder, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "menu:queue")
async def cb_queue(callback: CallbackQuery):
    conn = await db.get_conn()
    try:
        queue = await db.get_queue(conn, callback.from_user.id)
    finally:
        await conn.close()

    lines = ["📋 <b>Очередь клиентов</b>", ""]
    if not queue:
        lines.append("Пусто. Мойщики свободны — ждём клиентов.")
    else:
        for i, q in enumerate(queue, 1):
            svc = config.SERVICES[q["service_type"]]
            tag = " 🌟VIP" if q["is_vip"] else ""
            lines.append(f"{i}. {svc['name']}{tag}")
    lines.append("")
    lines.append("Мойка назначает мойщиков автоматически — тебе ничего делать не нужно 🙂")

    await callback.message.edit_text("\n".join(lines), reply_markup=kb.back_to_menu(), parse_mode="HTML")
    await callback.answer()
