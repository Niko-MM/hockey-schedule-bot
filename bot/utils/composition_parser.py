from typing import Dict, Any
from db.crud import find_player_by_surname


def parse_player_part(part: str) -> Dict[str, Any]:
    """
    Parse a single player part from a string

    Examples:
    "Петров 6" → {"surname": "Петров", "initial": None, "games": 6, "is_captain": False}
    "Петров А. 6" → {"surname": "Петров", "initial": "А", "games": 6, "is_captain": False}
    "Соколов М. 4" → {"surname": "Соколов", "initial": "М", "games": 4, "is_captain": False}
    "Петров (К) 6" → {"surname": "Петров", "initial": None, "games": 6, "is_captain": True}
    """
    part = part.strip()

    # Check for captain marker (both Russian 'К' and English 'k')
    is_captain = False
    captain_marker = None

    if '(к)' in part.lower():
        is_captain = True
        # Find and preserve the original marker
        if '(к)' in part:
            captain_marker = '(к)'
            part = part.replace('(к)', '').strip()
        elif '(К)' in part:
            captain_marker = '(К)'
            part = part.replace('(К)', '').strip()
        elif '(k)' in part:
            captain_marker = '(k)'
            part = part.replace('(k)', '').strip()
        elif '(K)' in part:
            captain_marker = '(K)'
            part = part.replace('(K)', '').strip()

    # Split into name/initial and games count
    if ' ' in part:
        *name_parts, games_str = part.rsplit(' ', 1)
        try:
            games = int(games_str)
        except ValueError:
            # Not a number - might be initial like "М."
            games = None
            name_parts.append(games_str)  # Add back to name_parts
        name = ' '.join(name_parts).strip()
    else:
        name = part.strip()
        games = None

    # Parse surname and initial
    # Handle formats: "Петров", "Петров А.", "Соколов М."
    surname = None
    initial = None

    if '.' in name:
        # Check if format is "Фамилия И." (initial as separate word)
        words = name.split()
        if len(words) == 2 and len(words[1]) == 2 and words[1].endswith('.'):
            # Format: "Соколов М."
            surname = words[0]
            initial = words[1][0].upper()
        elif len(words) == 1:
            # Format: "Петров А." (initial attached with dot)
            parts = name.split('.', 1)
            surname = parts[0].strip()
            initial = parts[1].strip()[0] if parts[1].strip() else None
        else:
            # Multiple words, complex format
            surname = words[0]
            # Check if second word is initial
            if len(words) >= 2 and len(words[1]) == 2 and words[1].endswith('.'):
                initial = words[1][0].upper()
    else:
        # No dot - just surname
        surname = name.strip()
        initial = None

    return {
        "surname": surname,
        "initial": initial,
        "games": games,
        "is_captain": is_captain,
        "captain_marker": captain_marker  # Preserve original marker for display
    }


def parse_slot(line: str, total_games: int, allow_extra_games: bool = False) -> Dict[str, Any]:
    """
    Parse a single line (slot) with players.

    When allow_extra_games=False (создание расписания):
    - Сумма игр в слоте должна быть ровно total_games.
    - Один игрок без числа получает остаток; несколько без числа — ошибка.

    When allow_extra_games=True (редактирование дня/прошлого):
    - Разрешена сумма больше total_games (игроки доигрывали за отсутствующих).
    - Один игрок без числа получает max(0, total_games - total_assigned).
    """
    line = line.strip()

    player_strings = line.split('/')
    players = []
    total_assigned = 0
    unassigned_indices = []

    for i, player_str in enumerate(player_strings):
        player_data = parse_player_part(player_str)
        players.append(player_data)

        if player_data["games"] is not None:
            total_assigned += player_data["games"]
        else:
            unassigned_indices.append(i)

    if len(unassigned_indices) > 1:
        return {
            "players": players,
            "valid": False,
            "error": f"Несколько игроков без игр ({len(unassigned_indices)}). Укажите количество игр для каждого."
        }

    if len(unassigned_indices) == 1:
        remaining = total_games - total_assigned
        if not allow_extra_games and remaining < 0:
            return {
                "players": players,
                "valid": False,
                "error": f"Сумма игр ({total_assigned}) превышает лимит ({total_games})"
            }
        idx = unassigned_indices[0]
        players[idx]["games"] = max(0, remaining)

    actual_sum = sum(p["games"] for p in players if p["games"] is not None)

    if not allow_extra_games:
        if actual_sum > total_games:
            return {
                "players": players,
                "valid": False,
                "error": f"Сумма игр ({actual_sum}) превышает лимит ({total_games})"
            }
        if actual_sum < total_games:
            return {
                "players": players,
                "valid": False,
                "error": f"Сумма игр ({actual_sum}) меньше лимита ({total_games}). Распределите все {total_games} игр."
            }

    return {
        "players": players,
        "valid": True,
        "error": None
    }


async def validate_team_composition(
    text: str,
    total_games: int,
    allow_extra_games: bool = False,
) -> Dict[str, Any]:
    """
    Validate entire team composition.

    allow_extra_games: при True (редактирование тура из БД) разрешена сумма игр
    в слоте/команде больше total_games — для учёта доигранных за отсутствующего.
    """
    lines = text.strip().split('\n')
    result = {
        "valid": True,
        "slots": [],
        "errors": [],
        "warnings": [],
    }

    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        slot_data = parse_slot(line, total_games, allow_extra_games=allow_extra_games)

        if not slot_data["valid"]:
            result["errors"].append(
                f"Слот {i}: {slot_data['error']}"
            )
            result["valid"] = False
            continue

        # Check each player in database
        for player_data in slot_data["players"]:
            player = await find_player_by_surname(
                player_data["surname"],
                player_data["initial"]
            )

            if player is None:
                result["errors"].append(
                    f"Слот {i}: Игрок '{player_data['surname']}' не найден в базе"
                )
                result["valid"] = False
            elif isinstance(player, list):
                # Multiple players found - only show warning if initial was NOT provided
                if not player_data["initial"]:
                    suggestions = [f"{p.surname} {p.name[0]}." for p in player]
                    result["warnings"].append(
                        f"⚠️ Слот {i}: Найдено несколько игроков с фамилией '{player_data['surname']}':\n" +
                        "\n".join([f"• {s}" for s in suggestions]) +
                        "\n\n" +
                        "❗️ **ПЕРЕПИШИТЕ ВЕСЬ СОСТАВ КОМАНДЫ ЗАНОВО**\n" +
                        "Укажите фамилию с первой буквой имени.\n\n" +
                        "Пример правильного ввода:\n" +
                        f"• {player_data['surname']} {player[0].name[0]}.\n" +
                        "• Петров\n" +
                        "• Иванов 5"
                    )
                    result["valid"] = False
                # If initial was provided and still multiple matches - accept first match
                # Update player_data with the correct initial from database
                elif len(player) >= 1:
                    first_player = player[0] if isinstance(player, list) else player
                    if first_player.name:
                        correct_initial = first_player.name[0].upper()
                        # Update initial in player_data
                        player_data["initial"] = correct_initial
                        player_data["surname"] = first_player.surname
            else:
                # Single player found - ensure initial matches
                if player_data["initial"] and player.name:
                    correct_initial = player.name[0].upper()
                    player_data["initial"] = correct_initial
                    player_data["surname"] = player.surname

        # Build display string for each player
        # Games count only when there are substitutions (several players in slot)
        show_games = len(slot_data["players"]) > 1
        slot_display = []
        for player_data in slot_data["players"]:
            display_parts = [player_data["surname"]]

            # Add initial if present
            if player_data.get("initial"):
                display_parts.append(f"{player_data['initial']}.")

            # Add captain marker if present (preserve original)
            if player_data.get("captain_marker"):
                display_parts.append(player_data["captain_marker"])

            # Add games only when slot has substitutions
            if show_games and player_data["games"] is not None:
                display_parts.append(str(player_data["games"]))

            slot_display.append(" ".join(display_parts))

        result["slots"].append({
            "line_number": i,
            "original": line,
            "players": slot_data["players"],
            "display": " / ".join(slot_display)  # Formatted for display
        })

    return result


def build_composition_error_message(validation_result: Dict[str, Any]) -> str:
    """
    Build user-facing error message for invalid team composition.
    validation_result: dict with "errors" and "warnings" lists from validate_team_composition.
    """
    error_msg = "❌ **ОШИБКА В СОСТАВЕ КОМАНДЫ**\n\n"

    if validation_result["errors"]:
        error_msg += "**Ошибки:**\n"
        for error in validation_result["errors"]:
            error_msg += f"• {error}\n"
        error_msg += "\n"

    if validation_result["warnings"]:
        error_msg += "**Предупреждения:**\n"
        for warning in validation_result["warnings"]:
            error_msg += f"{warning}\n\n"

    error_msg += "━━━━━━━━━━━━━━━━━━━━\n"
    error_msg += "💡 **Совет:** Введите всех игроков команды, каждый с новой строки.\n"
    error_msg += "Если фамилия повторяется — добавьте первую букву имени.\n\n"
    error_msg += "Пример:\n"
    error_msg += "```\n"
    error_msg += "Петров А.\n"
    error_msg += "Иванов\n"
    error_msg += "Соколов М. 5\n"
    error_msg += "```"

    return error_msg