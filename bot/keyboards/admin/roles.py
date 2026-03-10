"""Inline keyboards for role editor (toggle roles, save)."""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

ROLE_KEYS = ["player", "worker", "goalkeeper", "officer"]
ROLE_LABELS = {
    "player": "Игрок",
    "worker": "Работник",
    "goalkeeper": "Вратарь",
    "officer": "Офицер",
}


def get_roles_editor_keyboard(
    person_id: int,
    roles: dict[str, bool],
) -> InlineKeyboardMarkup:
    """
    Inline keyboard: one button per role (toggle on/off), then Save.
    callback_data: role_toggle:{person_id}:{role_key}, role_save:{person_id}.
    """
    builder = InlineKeyboardBuilder()
    for key in ROLE_KEYS:
        label = ROLE_LABELS[key]
        mark = "✅" if roles.get(key, False) else "❌"
        builder.button(
            text=f"{label} {mark}",
            callback_data=f"role_toggle:{person_id}:{key}",
        )
    builder.button(text="💾 Сохранить", callback_data=f"role_save:{person_id}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()
