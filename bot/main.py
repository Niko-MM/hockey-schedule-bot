from aiogram import Dispatcher, Bot
from db.session import init_db
import asyncio
from bot.config import bot_settings
from bot.handlers.registration import router as registration_router
from bot.handlers.admin.players import router as admin_players_router
from bot.handlers.admin.workers import router as admin_workers_router
from bot.handlers.admin.roles import router as admin_roles_router
from bot.handlers.admin.approval import router as admin_approval_router
from bot.handlers.admin.schedule import router as schedule_router
from bot.handlers.user.salary import router as user_salary_router
from bot.handlers.user.schedule import router as user_schedule_router


async def main():
    await init_db()
    bot = Bot(token=bot_settings.bot_token)
    dp = Dispatcher()
    dp.include_router(admin_approval_router)
    dp.include_router(registration_router)
    dp.include_router(admin_roles_router)
    dp.include_router(admin_players_router)
    dp.include_router(admin_workers_router)
    dp.include_router(schedule_router)
    dp.include_router(user_salary_router)
    dp.include_router(user_schedule_router)
    print('bot is working')
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
    

if __name__ == '__main__':
    asyncio.run(main()) 

