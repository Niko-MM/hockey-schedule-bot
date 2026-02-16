from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup


async def get_admin_main_keyboard() -> ReplyKeyboardMarkup:
    """keyboard for admin(main)"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 Расписание")
    builder.button(text="📥 Входящие")
    builder.button(text="⚙️ Управление")
    builder.button(text="👤 Личное")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


async def get_schedule_key_board() -> ReplyKeyboardMarkup:
    """Admin 📋 Расписание -> next way"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="➕ Составить расписание")
    builder.button(text="✏️ Редактировать расписание")
    builder.button(text="👷 Расписание работников")
    builder.button(text="👽 Расписание вратарей")
    builder.button(text="🔙  Назад")
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


async def get_control_key_board() -> ReplyKeyboardMarkup:
    """Admin ⚙️ Управление -> next way"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="✏️👤 Редактирование ролей")
    builder.button(text="️️⚠️ Штрафы")
    builder.button(text="⛔ Бан")
    builder.button(text="💰 Расчёт зарплаты")
    builder.button(text="🔙  Назад")
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


async def get_personal_key_board() -> ReplyKeyboardMarkup:
    """Admin 👤 Личное -> next way"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="💰 Зарплата")
    builder.button(text="️️🏆 Рейтинг")
    builder.button(text="🔙  Назад")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)
