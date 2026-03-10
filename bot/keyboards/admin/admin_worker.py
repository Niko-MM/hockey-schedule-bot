from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup


async def get_admin_worker_main_keyboard() -> ReplyKeyboardMarkup:
    """Main menu keyboard for worker admin."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 Расписание")
    builder.button(text="👷 Работники")
    builder.button(text="⚙️ Управление")
    builder.button(text="👤 Личное")
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)


async def get_worker_schedule_keyboard() -> ReplyKeyboardMarkup:
    """Worker admin 📋 Schedule submenu (create/edit + view other schedules)."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="➕ Составить расписание")
    builder.button(text="✏️ Редактировать расписание")
    builder.button(text="👥 Расписание игроков")
    builder.button(text="👽 Расписание вратарей")
    builder.button(text="🔙  Назад")
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


async def get_worker_control_keyboard() -> ReplyKeyboardMarkup:
    """Worker admin ⚙️ Control submenu (applications and salary)."""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 Заявки")
    builder.button(text="💰 Расчёт зарплаты")
    builder.button(text="🔙  Назад")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

