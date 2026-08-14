import os

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery

import db
import config
import keyboards as kb

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    conn = await db.get_conn()
    try:
        created = await db.create_user_if_not_exists(conn, message.from_user.id, message.from_user.username or "")
        user = await db.get_user(conn, message.from_user.id)
    finally:
        await conn.close()

    if created:
        text = (
            "🚿 Добро пожаловать в <b>CarWash Tycoon</b>!\n\n"
            f"Тебе досталась небольшая автомойка: 1 бокс и мойщик-новичок.\n"
            f"Стартовый капитал: {config.STARTING_BALANCE}💰\n\n"
            "Мойка работает сама — клиенты приходят и обслуживаются автоматически. "
            "Твоя задача — нанимать мойщиков, покупать оборудование и реагировать на события.\n\n"
            "Загляни в меню 👇"
        )
    else:
        text = f"С возвращением! Баланс: {round(user['balance'],1)}💰"

    await message.answer(text, reply_markup=kb.main_menu(), parse_mode="HTML")


@router.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery):
    await callback.message.edit_text("Главное меню:", reply_markup=kb.main_menu())
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer("Уже куплено ✅")
