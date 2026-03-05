from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_add_team_3_keyboard() -> InlineKeyboardMarkup:
    """Keyboard after team 2: 4 buttons in 2x2 grid"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить команду",
            callback_data="add_team_3"
        ),
        InlineKeyboardButton(
            text="✏️ Редактировать тур",
            callback_data="edit_tour"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить тур",
            callback_data="add_another_tour"
        ),
        InlineKeyboardButton(
            text="✅ Завершить расписание",
            callback_data="finish_schedule"
        )
    )

    return builder.as_markup()


def get_edit_team_select_keyboard(teams_count: int = 2) -> InlineKeyboardMarkup:
    """Keyboard for selecting which team to edit (1, 2, or 3)"""
    builder = InlineKeyboardBuilder()

    builder.button(text="1️⃣ Команда 1", callback_data="edit_team:1")
    builder.button(text="2️⃣ Команда 2", callback_data="edit_team:2")
    
    if teams_count == 3:
        builder.button(text="3️⃣ Команда 3", callback_data="edit_team:3")

    builder.adjust(2)  # 2 columns
    
    builder.row(
        InlineKeyboardButton(
            text="↩️ Назад",
            callback_data="back_to_tour_menu"
        )
    )

    return builder.as_markup()


def get_tour_complete_keyboard() -> InlineKeyboardMarkup:
    """Keyboard after tour is complete: add another tour or finish"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить тур",
            callback_data="add_another_tour"
        ),
        InlineKeyboardButton(
            text="✅ Завершить расписание",
            callback_data="finish_schedule"
        )
    )

    return builder.as_markup()


def get_final_confirm_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for final schedule: edit day, publish, or delete"""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✏️ Редактировать игровой день",
            callback_data="edit_schedule"
        ),
        InlineKeyboardButton(
            text="✅ Опубликовать",
            callback_data="confirm_publish"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="🗑️ Удалить",
            callback_data="delete_schedule"
        )
    )

    return builder.as_markup()


def get_tour_list_keyboard(tours_count: int, from_db: bool) -> InlineKeyboardMarkup:
    """List of tours: select one to edit. from_db=True for edit-past flow."""
    builder = InlineKeyboardBuilder()
    prefix = "edit_db_tour:" if from_db else "edit_draft_tour:"
    for i in range(1, tours_count + 1):
        builder.button(text=f"🔢 Тур {i}", callback_data=f"{prefix}{i}")
    builder.adjust(2)
    back_data = "back_to_edit_menu" if from_db else "back_to_preview"
    back_text = "✅ Завершить редактирование" if from_db else "↩️ Назад"
    builder.row(
        InlineKeyboardButton(text=back_text, callback_data=back_data)
    )
    return builder.as_markup()


def get_edit_tour_menu_keyboard(teams_count: int) -> InlineKeyboardMarkup:
    """Edit one tour: time, games, team 1/2/3, done."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⏰ Время", callback_data="edit_field:time")
    builder.button(text="🎮 Игры", callback_data="edit_field:games")
    builder.adjust(2)
    builder.button(text="1️⃣ Команда 1", callback_data="edit_field:team_1")
    builder.button(text="2️⃣ Команда 2", callback_data="edit_field:team_2")
    if teams_count >= 3:
        builder.button(text="3️⃣ Команда 3", callback_data="edit_field:team_3")
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="✅ Готово", callback_data="edit_tour_done"),
        InlineKeyboardButton(text="↩️ К списку туров", callback_data="back_to_tour_list")
    )
    return builder.as_markup()


def get_team3_confirm_keyboard() -> InlineKeyboardMarkup:
    """Keyboard after 3 teams: Edit tour, Add tour, Finish schedule (no Add team)."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✏️ Редактировать тур",
            callback_data="edit_tour"
        ),
        InlineKeyboardButton(
            text="➕ Добавить тур",
            callback_data="add_another_tour"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✅ Завершить расписание",
            callback_data="finish_schedule"
        )
    )

    return builder.as_markup()