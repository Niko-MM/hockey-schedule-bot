from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup


async def get_admin_worker_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Главное меню админа работников.
    Структура полностью повторяет меню админа игроков,
    но вместо кнопки «👥 Игроки» используется «👷 Работники».
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 Расписание")
    builder.button(text="👷 Работники")
    builder.button(text="⚙️ Управление")
    builder.button(text="👤 Личное")
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)


async def get_worker_schedule_keyboard() -> ReplyKeyboardMarkup:
    """
    Подменю «📋 Расписание» для админа работников.
    Структура аналогична расписанию админа игроков:
    - создание / редактирование расписания работников;
    - переходы к расписанию игроков и вратарей;
    - кнопка «Назад».
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text="➕ Составить расписание")
    builder.button(text="✏️ Редактировать расписание")
    builder.button(text="👥 Расписание игроков")
    builder.button(text="👽 Расписание вратарей")
    builder.button(text="🔙  Назад")
    builder.adjust(2, 2, 1)
    return builder.as_markup(resize_keyboard=True)


async def get_worker_control_keyboard() -> ReplyKeyboardMarkup:
    """
    Подменю «⚙️ Управление» для админа работников.
    Пока базовый набор: заявки по работникам и расчёт их зарплаты.
    При необходимости кнопки можно расширить.
    """
    builder = ReplyKeyboardBuilder()
    builder.button(text="📋 Заявки")
    builder.button(text="💰 Расчёт зарплаты")
    builder.button(text="🔙  Назад")
    builder.adjust(2, 1)
    return builder.as_markup(resize_keyboard=True)

