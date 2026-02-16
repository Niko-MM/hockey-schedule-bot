from aiogram import Router, F
from aiogram.types import Message
from bot.config import bot_settings
from bot.keyboards.admin.admin_player import (
    get_admin_main_keyboard,
      get_control_key_board,
      get_personal_key_board,
      get_schedule_key_board
)

router = Router(name="players")


@router.message(F.text == "🔙  Назад")
async def admin_button_back(msg: Message):
    if not msg.from_user:
        return

    if msg.from_user.id == bot_settings.admin_players:
        await msg.answer("Главное меню", reply_markup=await get_admin_main_keyboard())
        return


@router.message(F.text == "⚙️ Управление")
async def admin_control_button(msg: Message):
    if not msg.from_user:
        return

    if msg.from_user.id == bot_settings.admin_players:
        await msg.answer("⚙️ Управление", reply_markup=await get_control_key_board())
        return
    

@router.message(F.text == '👤 Личное')
async def admin_personal_button(msg: Message):
    if not msg.from_user:
        return

    if msg.from_user.id == bot_settings.admin_players:
        await msg.answer('👤 Личное', reply_markup=await get_personal_key_board())


@router.message(F.text == '📋 Расписание')
async def admin_schedule_button(msg: Message):
    if not msg.from_user:
        return

    if msg.from_user.id == bot_settings.admin_players:
        await msg.answer('📋 Расписание', reply_markup=await get_schedule_key_board())
