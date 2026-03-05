from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_first_role_keyboard(tg_id: int) -> InlineKeyboardMarkup:
    """
    First choosing role
    callback_data: "select_role:{tg_id}:{role}"
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Игрок",
        callback_data=f"select_role:{tg_id}:player"
    )
    builder.button(
        text="👷 Работник",
        callback_data=f"select_role:{tg_id}:worker"
    )
    builder.button(
        text="🥅 Вратарь",
        callback_data=f"select_role:{tg_id}:goalkeeper"
    )
    builder.button(
        text="👮 Офицер",
        callback_data=f"select_role:{tg_id}:officer"
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=f"reject:{tg_id}"
    )
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def get_save_or_add_keyboard(tg_id: int, role: str) -> InlineKeyboardMarkup:
    """keyboard after first role choosed"""
    builder = InlineKeyboardBuilder()

    builder.button(text="💾 Сохранить", callback_data=f"save:{tg_id}:{role}")
    builder.button(text="➕ Добавить", callback_data=f"add_second_role:{tg_id}:{role}")

    builder.adjust(2)
    return builder.as_markup()


def get_second_role_keyboard(tg_id: int, first_role: str) -> InlineKeyboardMarkup:
    """keyboard for second role (exclude first_role)"""
    builder = InlineKeyboardBuilder()
    
    roles = [
        ("✅ Игрок", "player"),
        ("👷 Работник", "worker"),
        ("🥅 Вратарь", "goalkeeper"),
        ("👮 Офицер", "officer")
    ]
    
    for text, role_value in roles:
        if role_value != first_role:
            builder.button(
                text=text,
                callback_data=f"save:{tg_id}:{first_role}:{role_value}"
            )
    
    builder.button(
        text="🔙 Назад",
        callback_data=f"back_to_first:{tg_id}"
    )
    
    builder.adjust(2, 2, 1) 
    return builder.as_markup()
