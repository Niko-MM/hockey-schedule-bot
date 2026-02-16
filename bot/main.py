from aiogram import Dispatcher, Bot
from db.session import init_db
import asyncio
from bot.config import bot_settings
from bot.handlers.registration import router as registration_router
from bot.handlers.admin.players import router as admin_players_router
from bot.handlers.admin.approval import router as admin_approval_router
from bot.handlers.admin.schedule import router as schedule_router 



async def main():
    await init_db()
    bot = Bot(token=bot_settings.bot_token)
    dp = Dispatcher()
    dp.include_router(admin_approval_router)
    dp.include_router(registration_router)
    dp.include_router(admin_players_router)
    dp.include_router(schedule_router)
    print('bot is working')
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
    

if __name__ == '__main__':
    asyncio.run(main()) 

