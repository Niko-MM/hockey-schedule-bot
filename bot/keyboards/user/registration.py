from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """creat confirm registration inlineKeyboad"""
    builder = InlineKeyboardBuilder()
    builder.button(text='Подтвердить ✅' ,callback_data='confirm')
    builder.button(text='Редактировать ✍🏻', callback_data='edit')
    builder.adjust(2)
    return builder.as_markup()
