from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_user_keyboard() -> ReplyKeyboardMarkup:
    """main keyboard for approved user (player/worker)"""
    builder = ReplyKeyboardBuilder()
    
    builder.button(text="📅 Расписание")
    builder.button(text="👮‍♂️ Штрафы")
    builder.button(text="🏆 Рейтинги")
    builder.button(text="📜 Правила")
    
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=False)