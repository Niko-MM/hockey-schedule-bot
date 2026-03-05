from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup


async def get_admin_main_keyboard() -> ReplyKeyboardMarkup:
    """keyboard for admin(main)"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 Расписание")
    builder.button(text="👥 Игроки")
    builder.button(text="⚙️ Управление")
    builder.button(text="👤 Личное")
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)


async def get_schedule_keyboard() -> ReplyKeyboardMarkup:
    """Admin 📋 Расписание -> next way"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="➕ Составить расписание")
    builder.button(text="✏️ Редактировать расписание")
    builder.button(text="👷 Расписание работников")
    builder.button(text="👽 Расписание вратарей")
    builder.button(text="🔙  Назад")
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


async def get_control_keyboard() -> ReplyKeyboardMarkup:
    """Admin ⚙️ Управление -> next way"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 Заявки")
    builder.button(text="✏️👤 Редактирование ролей")
    builder.button(text="⚠️ Штрафы")
    builder.button(text="⛔ Бан")
    builder.button(text="💰 Расчёт зарплаты")
    builder.button(text="🔙  Назад")
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


async def get_personal_keyboard() -> ReplyKeyboardMarkup:
    """Admin 👤 Личное -> next way"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="💰 Моя зарплата")
    builder.button(text="🏆 Рейтинги")
    builder.button(text="🔙  Назад")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)
