from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

WALLPAPER_URL = "https://t.me/bg/t1mtue80EUl4GgAAjgg1iIK09Ds"


def get_wallpaper_offer_keyboard() -> InlineKeyboardMarkup:
    """Offer chat wallpaper: open link or skip."""
    builder = InlineKeyboardBuilder()
    builder.button(text="Фон чата РХЛ", url=WALLPAPER_URL)
    builder.button(text="Пропустить", callback_data="skip_wallpaper")
    builder.adjust(1)
    return builder.as_markup()
