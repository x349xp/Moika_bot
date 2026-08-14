import time
import random

from aiogram import Router, F
from aiogram.types import CallbackQuery

import db
import config
import keyboards as kb
import game_logic

router = Router()


@router.callback_query(F.data == "menu:events")
async def cb_events(callback: CallbackQuery):
    conn = await db.get_conn()
    try:
        await game_logic.unlock_broken_bays(conn, callback.from_user.id)
        cur = await conn.execute(
            "SELECT * FROM pending_events WHERE owner_id=? AND resolved=0 AND expires_at>? ORDER BY created_at DESC",
            (callback.from_user.id, time.time()),
        )
        events = await cur.fetchall()

        cur2 = await conn.execute(
            "SELECT * FROM bays WHERE owner_id=? AND status='broken'", (callback.from_user.id,)
        )
        broken_bays = await cur2.fetchall()
        await conn.commit()
    finally:
        await conn.close()

    if not events and not broken_bays:
        await callback.message.edit_text(
            "🚨 <b>События</b>\n\nСейчас никаких активных событий нет. Всё спокойно 🙂",
            reply_markup=kb.back_to_menu(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    if broken_bays:
        bay = broken_bays[0]
        left_min = max(0, int((bay["broken_until"] - time.time()) / 60))
        text = (
            f"🔧 <b>Бокс #{bay['bay_id']} сломан</b>\n\n"
            f"Сам почини за {left_min} мин, либо заплати {config.BREAKDOWN_REPAIR_COST}💰 и почини сразу."
        )
        await callback.message.edit_text(text, reply_markup=kb.repair_menu(bay["bay_id"]), parse_mode="HTML")
        await callback.answer()
        return

    ev = events[0]
    if ev["event_type"] == "vip_client":
        text = (
            "🚗 <b>VIP-клиент хочет заехать!</b>\n\n"
            "Готов заплатить в 1.8× больше обычного за VIP-детейлинг, "
            "но нужен свободный бокс и Мастер/Легенда с керамикой прямо сейчас.\n\n"
            "Принять — клиент встанет в начало очереди с высшим приоритетом.\n"
            "Отклонить — клиент уедет."
        )
        await callback.message.edit_text(text, reply_markup=kb.vip_event_menu(ev["event_id"]), parse_mode="HTML")
        await callback.answer()
        return

    await callback.answer()


@router.callback_query(F.data.startswith("repair:"))
async def cb_repair(callback: CallbackQuery):
    bay_id = int(callback.data.split(":")[1])

    conn = await db.get_conn()
    try:
        user = await db.get_user(conn, callback.from_user.id)
        if user["balance"] < config.BREAKDOWN_REPAIR_COST:
            await callback.answer(f"Не хватает денег: нужно {config.BREAKDOWN_REPAIR_COST}💰", show_alert=True)
            return
        await conn.execute(
            "UPDATE users SET balance=? WHERE user_id=?",
            (user["balance"] - config.BREAKDOWN_REPAIR_COST, callback.from_user.id),
        )
        await conn.execute(
            "UPDATE bays SET status='free', broken_until=0 WHERE bay_id=? AND owner_id=?",
            (bay_id, callback.from_user.id),
        )
        await conn.commit()
    finally:
        await conn.close()

    await callback.answer("Бокс починен 🔧")
    await callback.message.edit_text("✅ Бокс снова в строю!", reply_markup=kb.back_to_menu())


@router.callback_query(F.data.startswith("vip:"))
async def cb_vip(callback: CallbackQuery):
    _, action, event_id = callback.data.split(":")
    event_id = int(event_id)

    conn = await db.get_conn()
    try:
        cur = await conn.execute("SELECT * FROM pending_events WHERE event_id=?", (event_id,))
        ev = await cur.fetchone()
        if not ev or ev["resolved"]:
            await callback.answer("Событие уже неактуально")
            return

        await conn.execute("UPDATE pending_events SET resolved=1 WHERE event_id=?", (event_id,))

        if action == "accept":
            await conn.execute(
                "INSERT INTO queue (owner_id, service_type, is_vip, created_at) VALUES (?, 'vip', 1, ?)",
                (callback.from_user.id, time.time() - 999999),  # искусственно старый timestamp -> в начало очереди
            )
            await conn.commit()
            await callback.answer("VIP-клиент добавлен в очередь 🌟")
            await callback.message.edit_text(
                "✅ Принято! Клиент встал в приоритетную очередь — как только освободится подходящий "
                "мойщик и бокс, заказ начнётся автоматически.",
                reply_markup=kb.back_to_menu(),
            )
        else:
            await conn.commit()
            await callback.answer("Клиент уехал")
            await callback.message.edit_text("❌ VIP-клиент отклонён.", reply_markup=kb.back_to_menu())
    finally:
        await conn.close()
