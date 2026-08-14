from aiogram import Router, F
from aiogram.types import CallbackQuery

import db
import config
import keyboards as kb

router = Router()


@router.callback_query(F.data == "menu:shop")
async def cb_shop(callback: CallbackQuery):
    conn = await db.get_conn()
    try:
        user = await db.get_user(conn, callback.from_user.id)
    finally:
        await conn.close()

    lines = [
        "🛒 <b>Магазин оборудования</b>",
        f"Баланс: {round(user['balance'],1)}💰",
        "",
        "Оборудование открывает новые услуги и повышает чек:",
    ]
    for eq_key in config.EQUIPMENT_ORDER:
        eq = config.EQUIPMENT[eq_key]
        svc_name = config.SERVICES[eq["unlocks"]]["name"]
        owned = "✅ куплено" if user[f"has_{eq_key}"] else f"{eq['price']}💰"
        lines.append(f"• {eq['name']} ({owned}) → открывает «{svc_name}»")

    await callback.message.edit_text("\n".join(lines), reply_markup=kb.shop_menu(user), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery):
    key = callback.data.split(":")[1]

    conn = await db.get_conn()
    try:
        user = await db.get_user(conn, callback.from_user.id)

        if key == "bay":
            price = config.BAY_PRICE
            if user["balance"] < price:
                await callback.answer(f"Не хватает денег: нужно {price}💰", show_alert=True)
                return
            await conn.execute(
                "UPDATE users SET balance=? WHERE user_id=?", (user["balance"] - price, callback.from_user.id)
            )
            await conn.execute("INSERT INTO bays (owner_id, status) VALUES (?, 'free')", (callback.from_user.id,))
            await conn.commit()
            await callback.answer("Новый бокс построен 🏗️")
            await callback.message.edit_text(
                f"✅ Открыт новый бокс!\nОстаток баланса: {round(user['balance']-price,1)}💰",
                reply_markup=kb.back_to_menu(),
            )
            return

        if key not in config.EQUIPMENT:
            await callback.answer("Неизвестный товар")
            return

        eq = config.EQUIPMENT[key]
        if user[f"has_{key}"]:
            await callback.answer("Уже куплено ✅")
            return
        if user["balance"] < eq["price"]:
            await callback.answer(f"Не хватает денег: нужно {eq['price']}💰", show_alert=True)
            return

        new_balance = user["balance"] - eq["price"]
        await conn.execute(
            f"UPDATE users SET balance=?, has_{key}=1 WHERE user_id=?", (new_balance, callback.from_user.id)
        )
        await conn.commit()
    finally:
        await conn.close()

    svc_name = config.SERVICES[eq["unlocks"]]["name"]
    await callback.answer(f"Куплено: {eq['name']} 🎉")
    await callback.message.edit_text(
        f"✅ Куплено: {eq['name']}\nТеперь доступна услуга «{svc_name}»\nОстаток баланса: {round(new_balance,1)}💰",
        reply_markup=kb.back_to_menu(),
    )
