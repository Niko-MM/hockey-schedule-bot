from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_slot_actions_keyboard(
    player_name: str,
    current_slot: int,
    games_assigned: int = 0,
    total_games: int = 10,
    has_substitutes: bool = False
) -> InlineKeyboardMarkup:
    """
    Keyboard after player selection:
    First button = add substitute, second = next slot
    """
    builder = InlineKeyboardBuilder()
    
    # First button: Add substitute
    if games_assigned == 0:
        sub_text = "🔄 Добавить замену"
    else:
        remaining = total_games - games_assigned
        sub_text = f"🔄 Добавить замену (+{remaining} игр)"
    
    builder.button(
        text=sub_text,
        callback_data="slot:add_substitute"
    )
    
    # Second button: Next slot
    if games_assigned == 0:
        next_text = f"➡️ Следующий слот (все {total_games} игр)"
    else:
        next_text = f"➡️ Следующий слот ({games_assigned}/{total_games})"
    
    builder.button(
        text=next_text,
        callback_data="slot:next_slot"
    )
    
    builder.adjust(1)  # 1 column — substitute first, next slot second
    
    return builder.as_markup()