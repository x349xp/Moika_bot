import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
import db
import game_logic
from handlers import start, station, hire, shop, events

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("carwash.bot")


async def game_loop(bot: Bot):
    """Глобальный фоновый цикл — крутит игру для всех пользователей независимо от того,
    открыт у них чат с ботом прямо сейчас или нет. Именно это даёт idle-механику:
    мойка работает и приносит доход, пока игрок офлайн."""
    while True:
        try:
            conn = await db.get_conn()
            try:
                user_ids = await db.get_all_user_ids(conn)
            finally:
                await conn.close()

            for user_id in user_ids:
                conn = await db.get_conn()
                try:
                    await game_logic.process_user_tick(conn, user_id, bot=bot)
                except Exception as e:
                    logger.exception(f"Ошибка тика для {user_id}: {e}")
                finally:
                    await conn.close()
        except Exception as e:
            logger.exception(f"Ошибка игрового цикла: {e}")

        await asyncio.sleep(config.TICK_INTERVAL)


async def main():
    await db.init_db()

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(station.router)
    dp.include_router(hire.router)
    dp.include_router(shop.router)
    dp.include_router(events.router)

    asyncio.create_task(game_loop(bot))

    logger.info("Бот запущен, начинаю polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
