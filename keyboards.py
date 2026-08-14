from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config


def main_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="🏢 Моя мойка", callback_data="menu:station")
    kb.button(text="👷 Мойщики", callback_data="menu:workers")
    kb.button(text="🛒 Магазин", callback_data="menu:shop")
    kb.button(text="📋 Очередь", callback_data="menu:queue")
    kb.button(text="🚨 События", callback_data="menu:events")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def back_to_menu():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    return kb.as_markup()


def hire_menu():
    kb = InlineKeyboardBuilder()
    for level in config.WORKER_ORDER:
        wl = config.WORKER_LEVELS[level]
        kb.button(text=f"{wl['name']} — {wl['price']}💰", callback_data=f"hire:{level}")
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def shop_menu(user_row):
    kb = InlineKeyboardBuilder()
    for eq in config.EQUIPMENT_ORDER:
        info = config.EQUIPMENT[eq]
        owned = user_row[f"has_{eq}"]
        label = f"✅ {info['name']}" if owned else f"{info['name']} — {info['price']}💰"
        kb.button(text=label, callback_data=f"noop" if owned else f"buy:{eq}")
    kb.button(text=f"➕ Доп. бокс — {config.BAY_PRICE}💰", callback_data="buy:bay")
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def repair_menu(bay_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text=f"🔧 Починить сейчас за {config.BREAKDOWN_REPAIR_COST}💰", callback_data=f"repair:{bay_id}")
    kb.button(text="⬅️ В меню", callback_data="menu:main")
    kb.adjust(1)
    return kb.as_markup()


def vip_event_menu(event_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принять VIP-клиента", callback_data=f"vip:accept:{event_id}")
    kb.button(text="❌ Отклонить", callback_data=f"vip:decline:{event_id}")
    kb.adjust(1)
    return kb.as_markup()
