from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.models import Person


def get_single_player_select_keyboard(
    players: list[Person],
    all_players: list[Person],
    current_team: int = 1,
    players_selected: int = 0,
    required_per_team: int = 4,
    page: int = 1,
    total_pages: int = 1,
    is_reserve_list: bool = False
) -> InlineKeyboardMarkup:
    """
    Keyboard for selecting ONE player at a time (3x3 grid = 9 players per page).
    """
    builder = InlineKeyboardBuilder()
    
    # Players grid — 3 columns × 3 rows = 9 players max per page
    for player in players:
        # Format name with initial if duplicate surname
        surname_duplicates = [
            p for p in all_players
            if p.surname.lower() == player.surname.lower() and p.id != player.id
        ]
        if surname_duplicates:
            initial = player.name[0].upper() if player.name else "?"
            display_name = f"{player.surname} {initial}."
        else:
            display_name = player.surname
        
        builder.button(
            text=f"👤 {display_name}",
            callback_data=f"pick:{player.id}"
        )
    
    builder.adjust(3)  # 3 columns → automatically creates 3 rows when 9 buttons
    
    # List switchers (always visible)
    main_text = "👥 Основные" if not is_reserve_list else "✅ Основные"
    reserve_text = "✅ Запасные" if is_reserve_list else "🔄 Запасные"
    
    builder.row(
        InlineKeyboardButton(text=main_text, callback_data="list:main"),
        InlineKeyboardButton(text=reserve_text, callback_data="list:reserve")
    )
    
    # Pagination (only if multiple pages)
    if total_pages > 1:
        prev_disabled = page == 1
        next_disabled = page == total_pages
        
        prev_text = "🚫" if prev_disabled else "⬅️"
        next_text = "🚫" if next_disabled else "➡️"
        
        builder.row(
            InlineKeyboardButton(
                text=prev_text,
                callback_data="page:prev" if not prev_disabled else "noop"
            ),
            InlineKeyboardButton(
                text=f"Стр. {page}/{total_pages}",
                callback_data="noop"
            ),
            InlineKeyboardButton(
                text=next_text,
                callback_data="page:next" if not next_disabled else "noop"
            )
        )
    
    # Progress info (static button)
    builder.row(
        InlineKeyboardButton(
            text=f"Команда {current_team}: {players_selected}/{required_per_team}",
            callback_data="noop"
        )
    )
    
    return builder.as_markup()