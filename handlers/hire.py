from aiogram import Router, F
from aiogram.types import CallbackQuery

import db
import config
import keyboards as kb

router = Router()


@router.callback_query(F.data.startswith("hire:"))
async def cb_hire(callback: CallbackQuery):
    level = callback.data.split(":")[1]
    wl = config.WORKER_LEVELS[level]

    conn = await db.get_conn()
    try:
        user = await db.get_user(conn, callback.from_user.id)
        if user["balance"] < wl["price"]:
            await callback.answer(f"Не хватает денег: нужно {wl['price']}💰", show_alert=True)
            return

        new_balance = user["balance"] - wl["price"]
        await conn.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, callback.from_user.id))
        await conn.execute(
            "INSERT INTO workers (owner_id, level, name, status) VALUES (?, ?, ?, 'idle')",
            (callback.from_user.id, level, wl["name"]),
        )
        await conn.commit()
    finally:
        await conn.close()

    await callback.answer(f"Нанят: {wl['name']} 🎉")
    await callback.message.edit_text(
        f"✅ {wl['name']} принят в штат!\nОстаток баланса: {round(new_balance,1)}💰",
        reply_markup=kb.back_to_menu(),
    )
