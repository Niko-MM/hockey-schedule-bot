from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_schedule_keyboard(date_tour_id: int) -> InlineKeyboardMarkup:
    """
    Keyboard for schedule management.
    Buttons: add tour, publish, delete.
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🗑 Удалить",
        callback_data=f"delete_schedule:{date_tour_id}"
    )
    
    builder.button(
        text="➕ Добавить тур",
        callback_data=f"add_tour:{date_tour_id}"
    )
    builder.button(
        text="✅ Опубликовать",
        callback_data=f"publish_schedule:{date_tour_id}"
    )
    
    builder.adjust(2, 1)
    return builder.as_markup()


def get_teams_complete_keyboard(teams_count: int) -> InlineKeyboardMarkup:
    """
    Keyboard shown after all teams are filled.
    For 2 teams: offer captain selection.
    For 3 teams: go directly to confirmation.
    """
    builder = InlineKeyboardBuilder()
    
    # Edit teams button (always available)
    builder.row(
        InlineKeyboardButton(
            text="✏️ Редактировать состав",
            callback_data="edit_teams"
        )
    )
    
    # Next step depends on teams count
    if teams_count == 2:
        builder.row(
            InlineKeyboardButton(
                text="👑 Выбрать капитанов",
                callback_data="select_captains"
            )
        )
    else:  # 3 teams
        builder.row(
            InlineKeyboardButton(
                text="✅ Завершить тур",
                callback_data="confirm_schedule"
            )
        )
    
    return builder.as_markup()


