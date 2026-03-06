from aiogram import Bot, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from bot.states.schedule import ScheduleCreation
from bot.config import bot_settings
from bot.services.schedule_notifications import (
    build_player_schedule_message,
    notify_players_schedule_changed,
    send_full_schedule_to_players,
)
from db.crud import (
    create_tournament_day,
    get_date_tour_by_date,
    get_tours_by_date_tour_id,
    save_schedule_to_db,
    update_tour as update_tour_db,
)
from bot.utils.composition_parser import validate_team_composition, build_composition_error_message
from bot.keyboards.admin.schedule import (
    get_add_team_3_keyboard,
    get_final_confirm_keyboard,
    get_team3_confirm_keyboard,
    get_edit_team_select_keyboard, 
    get_tour_list_keyboard,
    get_edit_tour_menu_keyboard,
)
from bot.utils.date_parser import (
    parse_date_ddmmyy,
    get_weekday_short,
    normalize_time_hhmm,
    get_weekday_full,
    get_date_day_month,
)
from datetime import date


router = Router(name="admin_schedule")


@router.message(F.text == "➕ Составить расписание")
async def start_schedule_creation(msg: Message, state: FSMContext):
    """Start schedule creation: ask for tournament date"""
    if not msg.from_user:
        return

    if msg.from_user.id != bot_settings.admin_players:
        return

    await state.clear()
    await state.set_state(ScheduleCreation.waiting_for_date)
    await msg.answer(
        "📅 Создание расписания.\n"
        "Введите дату в формате ДД.ММ.ГГ"
    )


@router.message(ScheduleCreation.waiting_for_date)
async def process_date(msg: Message, state: FSMContext):
    """Parse date — block past dates, proceed to time input"""
    if not msg.text:
        await msg.answer("❌ Введите дату в формате ДД.ММ.ГГ")
        return

    parsed_date = parse_date_ddmmyy(msg.text)
    if not parsed_date:
        await msg.answer(
            "❌ Неверный формат даты.\nПример правильного формата: 25.02.26"
        )
        return

    # Allow past dates for testing (restriction was: parsed_date < today)
    # Get existing day or create new one
    existing_date_tour = await get_date_tour_by_date(parsed_date)
    if existing_date_tour:
        date_tour = existing_date_tour
    else:
        try:
            date_tour = await create_tournament_day(parsed_date)
        except ValueError as e:
            await msg.answer(f"❌ {e}")
            return

    await state.update_data(
        date_tour_id=date_tour.id,
        schedule_date=parsed_date.isoformat()
    )
    await state.set_state(ScheduleCreation.waiting_for_time)

    weekday = get_weekday_short(parsed_date)
    await msg.answer(
        f"✅ Дата расписания: {weekday}, {parsed_date:%d.%m.%Y}\n\n"
        "⏰ Введите время тура (ЧЧ:ММ)\n"
        "Пример: 08:30"
    )


@router.message(ScheduleCreation.waiting_for_time)
async def process_time(msg: Message, state: FSMContext):
    """Validate and normalize tour time"""
    if not msg.text:
        await msg.answer("❌ Введите время в формате ЧЧ:ММ")
        return

    normalized_time = normalize_time_hhmm(msg.text)
    if not normalized_time:
        await msg.answer(
            "❌ Неверный формат времени.\n"
            "Пример правильного формата: 05:00, 8:30 или 19:30"
        )
        return

    data = await state.get_data()
    schedule_date = data.get("schedule_date")

    if not schedule_date:
        await msg.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        return

    tour_date = date.fromisoformat(schedule_date)
    weekday = get_weekday_short(tour_date)

    await state.update_data(tour_time=normalized_time)
    await state.set_state(ScheduleCreation.waiting_for_games)

    await msg.answer(
        f"📅 {weekday}, {tour_date:%d.%m.%Y}\n"
        f"⏰ Время: {normalized_time}\n\n"
        "🎮 Введите количество игр в туре"
    )


@router.message(ScheduleCreation.waiting_for_games)
async def process_games(msg: Message, state: FSMContext):
    """Validate games count (1-20)"""
    if not msg.text:
        await msg.answer("❌ Введите количество игр (число от 1 до 20)")
        return

    try:
        games_count = int(msg.text.strip())
        if games_count < 1 or games_count > 20:
            raise ValueError
    except ValueError:
        await msg.answer(
            "❌ Неверное количество игр.\n"
            "Введите число от 1 до 20 (например: 5)"
        )
        return

    await state.update_data(games_count=games_count)
    await state.set_state(ScheduleCreation.waiting_for_team_1_composition)

    data = await state.get_data()
    schedule_date = data.get("schedule_date")
    tour_time = data.get("tour_time")

    if not schedule_date or not tour_time:
        await msg.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        return

    tour_date = date.fromisoformat(schedule_date)
    weekday = get_weekday_short(tour_date)

    await msg.answer(
        f"✅ Тур настроен:\n"
        f"📅 {weekday}, {tour_date:%d.%m.%Y} | ⏰ {tour_time}\n"
        f"🎮 {games_count} игр\n\n"
        f"📝 Введите состав команды 1:\n"
        f"Каждый игрок с новой строки.\n"
        f"Формат: Фамилия Количество/Замена Количество"
    )


@router.message(ScheduleCreation.waiting_for_team_1_composition)
async def process_team_1_composition(msg: Message, state: FSMContext):
    """Process team 1 composition"""
    if not msg.text:
        await msg.answer("❌ Введите состав команды")
        return

    composition_text = msg.text.strip()
    data = await state.get_data()
    games_count = data.get("games_count", 10)

    validation_result = await validate_team_composition(composition_text, games_count)

    if not validation_result["valid"]:
        await msg.answer(
            build_composition_error_message(validation_result),
            parse_mode="Markdown",
        )
        return

    # Build formatted composition from validation result
    formatted_composition = "\n".join(
        slot["display"] for slot in validation_result["slots"]
    )

    await state.update_data(team_1_composition=formatted_composition)
    await state.set_state(ScheduleCreation.waiting_for_team_2_composition)

    data = await state.get_data()
    schedule_date = data.get("schedule_date")
    tour_time = data.get("tour_time")
    games_count = data.get("games_count")

    if not schedule_date or not tour_time or not games_count:
        await msg.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        return

    tour_date = date.fromisoformat(schedule_date)
    weekday = get_weekday_short(tour_date)

    await msg.answer(
        f"✅ Команда 1 сохранена!\n"
        f"📅 {weekday}, {tour_date:%d.%m.%Y} | ⏰ {tour_time}\n"
        f"🎮 {games_count} игр\n\n"
        f"Команда 1:\n{formatted_composition}\n\n"
        f"📝 Введите состав команды 2:"
    )


@router.message(ScheduleCreation.waiting_for_team_2_composition)
async def process_team_2_composition(msg: Message, state: FSMContext):
    """Process team 2 composition and show action keyboard"""
    if not msg.text:
        await msg.answer("❌ Введите состав команды")
        return

    composition_text = msg.text.strip()
    data = await state.get_data()
    games_count = data.get("games_count", 10)

    validation_result = await validate_team_composition(composition_text, games_count)

    if not validation_result["valid"]:
        await msg.answer(
            build_composition_error_message(validation_result),
            parse_mode="Markdown",
        )
        return

    # Build formatted composition from validation result
    formatted_composition = "\n".join(
        slot["display"] for slot in validation_result["slots"]
    )

    await state.update_data(team_2_composition=formatted_composition)

    data = await state.get_data()
    schedule_date = data.get("schedule_date")
    tour_time = data.get("tour_time")
    games_count = data.get("games_count")
    team_1_composition = data.get("team_1_composition", "")

    if not schedule_date or not tour_time or not games_count:
        await msg.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        return

    tour_date = date.fromisoformat(schedule_date)
    weekday = get_weekday_short(tour_date)

    await msg.answer(
        f"✅ Команда 2 сохранена!\n\n"
        f"📅 {weekday}, {tour_date:%d.%m.%Y} | ⏰ {tour_time}\n"
        f"🎮 {games_count} игр\n\n"
        f"Команда 1:\n{team_1_composition}\n\n"
        f"Команда 2:\n{formatted_composition}\n\n"
        f"Выберите действие:",
        reply_markup=get_add_team_3_keyboard(),
    )


@router.callback_query(F.data == "add_team_3")
async def handle_add_team_3(callback: CallbackQuery, state: FSMContext):
    """Handle adding team 3"""
    if not callback.message:
        await callback.answer()
        return

    await state.set_state(ScheduleCreation.waiting_for_team_3_composition)

    data = await state.get_data()
    schedule_date = data.get("schedule_date")
    tour_time = data.get("tour_time")
    games_count = data.get("games_count")
    team_1_composition = data.get("team_1_composition", "")
    team_2_composition = data.get("team_2_composition", "")

    if not schedule_date or not tour_time or not games_count:
        await callback.message.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        await callback.answer()
        return

    tour_date = date.fromisoformat(schedule_date)
    weekday = get_weekday_short(tour_date)

    await callback.message.answer(
        f"📅 {weekday}, {tour_date:%d.%m.%Y} | ⏰ {tour_time}\n"
        f"🎮 {games_count} игр\n\n"
        f"Команда 1:\n{team_1_composition}\n\n"
        f"Команда 2:\n{team_2_composition}\n\n"
        f"📝 Введите состав команды 3:"
    )
    await callback.answer()


@router.callback_query(F.data == "finish_schedule")
async def handle_finish_schedule(callback: CallbackQuery, state: FSMContext):
    """Handle finishing schedule creation and show final preview"""
    if not callback.message:
        await callback.answer()
        return

    data = await state.get_data()
    schedule_date = data.get("schedule_date")
    tour_time = data.get("tour_time")
    games_count = data.get("games_count")
    team_1_composition = data.get("team_1_composition", "")
    team_2_composition = data.get("team_2_composition", "")
    team_3_composition = data.get("team_3_composition")

    if not schedule_date or not tour_time or not games_count:
        await callback.message.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        await callback.answer()
        return

    teams_count = 2
    if team_3_composition:
        teams_count = 3

    current_tour = {
        "time": tour_time,
        "games": games_count,
        "teams_count": teams_count,
        "team_1_composition": team_1_composition,
        "team_2_composition": team_2_composition,
        "team_3_composition": team_3_composition
    }

    tours = data.get("tours", [])
    tours.append(current_tour)
    await state.update_data(tours=tours)

    tour_date = date.fromisoformat(schedule_date)

    # То же форматирование, что видят игроки
    player_view = build_player_schedule_message(tour_date, tours)
    message_text = "📋 ИТОГОВОЕ РАСПИСАНИЕ\n\n"
    message_text += player_view
    message_text += "\nТак это расписание увидят игроки.\n\nВыберите действие:"

    await callback.message.answer(
        message_text,
        reply_markup=get_final_confirm_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "edit_tour")
async def handle_edit_tour(callback: CallbackQuery, state: FSMContext):
    """Show team selection for editing"""
    if not callback.message:
        await callback.answer()
        return

    data = await state.get_data()
    teams_count = data.get("teams_count", 2)
    
    # If team_3_composition exists, we have 3 teams
    if data.get("team_3_composition"):
        teams_count = 3

    await callback.message.answer(
        "✏️ Редактирование тура\n\n"
        "Выберите команду для редактирования:",
        reply_markup=get_edit_team_select_keyboard(teams_count)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_team:"))
async def handle_edit_team_select(callback: CallbackQuery, state: FSMContext):
    """Handle team selection for editing"""
    if not callback.message:
        await callback.answer()
        return
    
    if not callback.data:
        return

    try:
        team_number = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка")
        return

    data = await state.get_data()
    
    # Get the selected team composition
    if team_number == 1:
        composition = data.get("team_1_composition", "")
    elif team_number == 2:
        composition = data.get("team_2_composition", "")
    else:
        composition = data.get("team_3_composition", "")

    if not composition:
        await callback.answer("❌ Команда не найдена", show_alert=True)
        return

    # Save context for editing
    await state.update_data(editing_team=team_number)
    await state.set_state(ScheduleCreation.waiting_for_team_edit)

    # Send composition without any extra text (easy to copy)
    await callback.message.answer(composition)
    await callback.answer()


@router.message(ScheduleCreation.waiting_for_team_edit)
async def process_team_edit(msg: Message, state: FSMContext):
    """Process edited team composition"""
    if not msg.text:
        await msg.answer("❌ Введите состав команды")
        return

    composition_text = msg.text.strip()
    data = await state.get_data()
    editing_team = data.get("editing_team")
    games_count = data.get("games_count", 10)

    if not editing_team:
        await msg.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        return

    # Validate the new composition
    validation_result = await validate_team_composition(composition_text, games_count)

    if not validation_result["valid"]:
        await msg.answer(
            build_composition_error_message(validation_result),
            parse_mode="Markdown",
        )
        return

    # Update the team composition
    if editing_team == 1:
        await state.update_data(team_1_composition=composition_text)
    elif editing_team == 2:
        await state.update_data(team_2_composition=composition_text)
    else:
        await state.update_data(team_3_composition=composition_text)

    # Save team number for message before clearing
    updated_team_number = editing_team

    # Clear editing state
    await state.update_data(editing_team=None)
    await state.set_state(None)

    # Show updated tour with all teams
    data = await state.get_data()
    schedule_date = data.get("schedule_date")
    tour_time = data.get("tour_time")
    games_count = data.get("games_count")
    team_1 = data.get("team_1_composition", "")
    team_2 = data.get("team_2_composition", "")
    team_3 = data.get("team_3_composition")

    if not schedule_date or not tour_time or not games_count:
        await msg.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        return

    tour_date = date.fromisoformat(schedule_date)
    weekday = get_weekday_short(tour_date)

    message_text = f"✅ Команда {updated_team_number} обновлена!\n\n"
    message_text += f"📅 {weekday}, {tour_date:%d.%m.%Y} | ⏰ {tour_time}\n"
    message_text += f"🎮 {games_count} игр\n\n"
    message_text += "────────────────────\n\n"
    message_text += f"Команда 1:\n{team_1}\n\n"
    message_text += f"Команда 2:\n{team_2}\n"
    if team_3:
        message_text += f"\nКоманда 3:\n{team_3}\n"

    await msg.answer(
        message_text,
        reply_markup=get_add_team_3_keyboard()
    )


@router.callback_query(F.data == "back_to_tour_menu")
async def handle_back_to_tour_menu(callback: CallbackQuery, state: FSMContext):
    """Go back to tour editing menu"""
    if not callback.message:
        await callback.answer()
        return

    # Just acknowledge and let user continue
    await callback.message.answer("↩️ Возврат в меню редактирования")
    await callback.answer()


@router.callback_query(F.data == "add_another_tour")
async def handle_add_another_tour(callback: CallbackQuery, state: FSMContext):
    """Handle adding another tour — save current tour and start new one."""
    if not callback.message:
        await callback.answer()
        return

    data = await state.get_data()
    schedule_date = data.get("schedule_date")
    tours = data.get("tours", [])
    tour_time = data.get("tour_time")
    games_count = data.get("games_count")
    team_1_composition = data.get("team_1_composition", "")
    team_2_composition = data.get("team_2_composition", "")
    team_3_composition = data.get("team_3_composition")

    if not schedule_date or not tour_time or not games_count:
        await callback.message.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        await callback.answer()
        return

    # Save current tour into list
    teams_count = 2
    if team_3_composition:
        teams_count = 3

    current_tour = {
        "time": tour_time,
        "games": games_count,
        "teams_count": teams_count,
        "team_1_composition": team_1_composition,
        "team_2_composition": team_2_composition,
        "team_3_composition": team_3_composition,
    }

    tours.append(current_tour)
    # Очищаем состав третьей команды, чтобы следующий тур не унаследовал его
    await state.update_data(tours=tours, team_3_composition=None)

    tour_date = date.fromisoformat(schedule_date)
    weekday = get_weekday_short(tour_date)

    # Show previous tours with full compositions
    message_text = f"📅 {weekday}, {tour_date:%d.%m.%Y}\n\n"
    message_text += f"➕ Добавление тура #{len(tours) + 1}\n\n"

    if tours:
        message_text += "📋 Ранее добавленные туры:\n\n"
        for i, tour in enumerate(tours, 1):
            message_text += f"🔢 Тур {i} | ⏰ {tour['time']} | 🎮 {tour['games']} игр\n"
            message_text += f"Команда 1:\n{tour['team_1_composition']}\n\n"
            message_text += f"Команда 2:\n{tour['team_2_composition']}\n"
            if tour.get("team_3_composition"):
                message_text += f"Команда 3:\n{tour['team_3_composition']}\n"
            message_text += "\n────────────────────\n\n"

    message_text += "⏰ Введите время нового тура (ЧЧ:ММ)\nПример: 15:40"

    await state.set_state(ScheduleCreation.waiting_for_time)
    await callback.message.answer(message_text)
    await callback.answer()


def _format_tour_list_message(tour_date: date, tours: list[dict], title: str = "📋 Редактирование игрового дня") -> str:
    """Build message text for list of tours (draft or from DB)."""
    weekday = get_weekday_short(tour_date)
    msg = f"{title}\n\n📅 {weekday}, {tour_date:%d.%m.%Y}\n\n"
    for i, t in enumerate(tours, 1):
        msg += f"🔢 Тур {i} | ⏰ {t.get('time', '')} | 🎮 {t.get('games', 0)} игр\n"
    msg += "\nВыберите тур для редактирования:"
    return msg


def _format_edit_tour_message(tour: dict, tour_date: date) -> str:
    """Build message text for single tour edit menu."""
    weekday = get_weekday_short(tour_date)
    msg = f"✏️ Тур | 📅 {weekday}, {tour_date:%d.%m.%Y}\n\n"
    msg += f"⏰ {tour.get('time', '')} | 🎮 {tour.get('games', 0)} игр\n\n"
    msg += f"Команда 1:\n{tour.get('team_1_composition', '')}\n\n"
    msg += f"Команда 2:\n{tour.get('team_2_composition', '')}\n"
    if tour.get("team_3_composition"):
        msg += f"\nКоманда 3:\n{tour['team_3_composition']}\n"
    msg += "\nЧто изменить?"
    return msg


@router.callback_query(F.data == "edit_schedule")
async def handle_edit_schedule(callback: CallbackQuery, state: FSMContext):
    """From final preview: show draft tour list for editing this day."""
    if not callback.message:
        await callback.answer()
        return

    data = await state.get_data()
    schedule_date = data.get("schedule_date")
    tours = data.get("tours", [])

    if not schedule_date or not tours:
        await callback.message.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        await callback.answer()
        return

    tour_date = date.fromisoformat(schedule_date)
    await callback.message.answer(
        _format_tour_list_message(tour_date, tours),
        reply_markup=get_tour_list_keyboard(len(tours), from_db=False),
    )
    await state.update_data(edit_mode_from_db=False)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_draft_tour:"))
async def handle_edit_draft_tour(callback: CallbackQuery, state: FSMContext):
    """Select a draft tour to edit (from final preview)."""
    if not callback.message or not callback.data:
        await callback.answer()
        return

    try:
        i = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка")
        return

    data = await state.get_data()
    tours = data.get("tours", [])
    schedule_date = data.get("schedule_date")

    if i < 1 or i > len(tours) or not schedule_date:
        await callback.answer("❌ Ошибка")
        return

    tour = tours[i - 1]
    tour_date = date.fromisoformat(schedule_date)
    teams_count = tour.get("teams_count", 2)

    await state.update_data(
        editing_tour_index=i,
        edit_mode_from_db=False,
        tour_time=tour.get("time"),
        games_count=tour.get("games"),
        team_1_composition=tour.get("team_1_composition", ""),
        team_2_composition=tour.get("team_2_composition", ""),
        team_3_composition=tour.get("team_3_composition"),
    )
    await callback.message.answer(
        _format_edit_tour_message(tour, tour_date),
        reply_markup=get_edit_tour_menu_keyboard(teams_count),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_db_tour:"))
async def handle_edit_db_tour(callback: CallbackQuery, state: FSMContext):
    """Select a saved tour to edit (from edit-past flow)."""
    if not callback.message or not callback.data:
        await callback.answer()
        return

    try:
        i = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка")
        return

    data = await state.get_data()
    tours = data.get("tours", [])
    schedule_date = data.get("schedule_date")

    if i < 1 or i > len(tours) or not schedule_date:
        await callback.answer("❌ Ошибка")
        return

    tour = tours[i - 1]
    tour_date = date.fromisoformat(schedule_date)
    teams_count = tour.get("teams_count", 2)

    await state.update_data(
        editing_tour_index=i,
        editing_tour_id=tour.get("id"),
        edit_mode_from_db=True,
        tour_time=tour.get("time"),
        games_count=tour.get("games"),
        team_1_composition=tour.get("team_1_composition", ""),
        team_2_composition=tour.get("team_2_composition", ""),
        team_3_composition=tour.get("team_3_composition"),
    )
    await callback.message.answer(
        _format_edit_tour_message(tour, tour_date),
        reply_markup=get_edit_tour_menu_keyboard(teams_count),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field:"))
async def handle_edit_field(callback: CallbackQuery, state: FSMContext):
    """Start editing one field: time, games, or team 1/2/3."""
    if not callback.message or not callback.data:
        await callback.answer()
        return

    field = callback.data.split(":")[1]
    prompts = {
        "time": "⏰ Введите время тура (ЧЧ:ММ)\nПример: 08:30",
        "games": "🎮 Введите количество игр (1–20)",
        "team_1": "📝 Введите состав команды 1:",
        "team_2": "📝 Введите состав команды 2:",
        "team_3": "📝 Введите состав команды 3:",
    }
    if field not in prompts:
        await callback.answer()
        return

    await state.update_data(editing_field=field)
    await state.set_state(ScheduleCreation.waiting_for_edit_value)
    text = prompts[field]
    data = await state.get_data()
    if field.startswith("team_") and data.get("edit_mode_from_db"):
        text += "\n\n💡 Можно указать игроку больше игр, чем в туре (если доигрывал за отсутствующего)."
    await callback.message.answer(text)
    await callback.answer()


@router.message(ScheduleCreation.waiting_for_edit_value)
async def process_edit_value(msg: Message, state: FSMContext):
    """Process edited value and update tour (draft in state or prepare for DB save on Done)."""
    if not msg.text:
        await msg.answer("❌ Введите значение")
        return

    data = await state.get_data()
    field = data.get("editing_field")
    editing_tour_index = data.get("editing_tour_index")
    tours = data.get("tours", [])

    if not field or not editing_tour_index or editing_tour_index > len(tours):
        await msg.answer("❌ Ошибка состояния.")
        await state.set_state(None)
        return

    tour = dict(tours[editing_tour_index - 1])
    schedule_date = data.get("schedule_date")
    tour_date = date.fromisoformat(schedule_date) if schedule_date else date.today()

    if field == "time":
        normalized = normalize_time_hhmm(msg.text.strip())
        if not normalized:
            await msg.answer("❌ Неверный формат времени. Пример: 08:30")
            return
        tour["time"] = normalized
    elif field == "games":
        try:
            games_count = int(msg.text.strip())
            if games_count < 1 or games_count > 20:
                raise ValueError
        except ValueError:
            await msg.answer("❌ Введите число от 1 до 20")
            return
        tour["games"] = games_count
    elif field in ("team_1", "team_2", "team_3"):
        composition_text = msg.text.strip()
        games_count = tour.get("games", 10)
        # При редактировании тура из БД разрешаем игры выше лимита тура (доиграл за отсутствующего)
        from_db = data.get("edit_mode_from_db", False)
        validation_result = await validate_team_composition(
            composition_text, games_count, allow_extra_games=from_db
        )
        if not validation_result["valid"]:
            await msg.answer(
                build_composition_error_message(validation_result),
                parse_mode="Markdown",
            )
            return
        formatted = "\n".join(slot["display"] for slot in validation_result["slots"])
        key = "team_1_composition" if field == "team_1" else "team_2_composition" if field == "team_2" else "team_3_composition"
        tour[key] = formatted
        if field == "team_1":
            await state.update_data(team_1_composition=formatted)
        elif field == "team_2":
            await state.update_data(team_2_composition=formatted)
        else:
            await state.update_data(team_3_composition=formatted)

    tours[editing_tour_index - 1] = tour
    await state.update_data(tours=tours, editing_field=None)
    await state.set_state(None)

    teams_count = tour.get("teams_count", 2)
    await msg.answer(
        _format_edit_tour_message(tour, tour_date),
        reply_markup=get_edit_tour_menu_keyboard(teams_count),
    )


@router.callback_query(F.data == "edit_tour_done")
async def handle_edit_tour_done(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Finish editing one tour. Persist to DB if edit-past, then show tour list."""
    if not callback.message:
        await callback.answer()
        return

    data = await state.get_data()
    editing_tour_index = data.get("editing_tour_index")
    from_db = data.get("edit_mode_from_db", False)
    schedule_date = data.get("schedule_date")
    tours = data.get("tours", [])

    if not editing_tour_index or editing_tour_index > len(tours):
        await callback.message.answer("❌ Ошибка состояния.")
        await state.clear()
        await callback.answer()
        return

    tour = tours[editing_tour_index - 1]
    tour_date = date.fromisoformat(schedule_date) if schedule_date else date.today()

    if from_db:
        tour_id = data.get("editing_tour_id")
        if not tour_id:
            await callback.message.answer("❌ Ошибка: тур не найден.")
            await callback.answer()
            return
        try:
            updated = await update_tour_db(
                tour_id=tour_id,
                time=tour.get("time", ""),
                games=tour.get("games", 0),
                teams_count=tour.get("teams_count", 2),
                team_1_composition=tour.get("team_1_composition", ""),
                team_2_composition=tour.get("team_2_composition", ""),
                team_3_composition=tour.get("team_3_composition"),
            )
            if updated:
                await notify_players_schedule_changed(tour_date, bot)
        except Exception as e:
            await callback.message.answer(f"❌ Ошибка сохранения: {e}")
            await callback.answer()
            return
        # Reload tours from DB
        date_tour_id = data.get("date_tour_id")
        if not isinstance(date_tour_id, int):
            await callback.message.answer("❌ Ошибка состояния: не указан игровой день.")
            await callback.answer()
            return

        db_tours = await get_tours_by_date_tour_id(date_tour_id)
        tours = [
            {
                "id": t.id,
                "time": t.time,
                "games": t.games,
                "teams_count": t.teams_count,
                "team_1_composition": t.team_1_composition or "",
                "team_2_composition": t.team_2_composition or "",
                "team_3_composition": t.team_3_composition,
            }
            for t in db_tours
        ]
        await state.update_data(tours=tours)

    await state.update_data(editing_tour_index=None, editing_tour_id=None)
    await callback.message.answer(
        "✅ Изменения сохранены.",
    )
    await callback.message.answer(
        _format_tour_list_message(tour_date, tours),
        reply_markup=get_tour_list_keyboard(len(tours), from_db=from_db),
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_tour_list")
async def handle_back_to_tour_list(callback: CallbackQuery, state: FSMContext):
    """Return to tour list from edit menu (without saving in DB mode)."""
    if not callback.message:
        await callback.answer()
        return

    data = await state.get_data()
    from_db = data.get("edit_mode_from_db", False)
    schedule_date = data.get("schedule_date")
    tours = data.get("tours", [])

    await state.update_data(editing_tour_index=None, editing_tour_id=None)

    if not schedule_date or not tours:
        await callback.message.answer("❌ Ошибка состояния.")
        await callback.answer()
        return

    tour_date = date.fromisoformat(schedule_date)
    await callback.message.answer(
        _format_tour_list_message(tour_date, tours),
        reply_markup=get_tour_list_keyboard(len(tours), from_db=from_db),
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_preview")
async def handle_back_to_preview(callback: CallbackQuery, state: FSMContext):
    """Return to final schedule preview from draft tour list."""
    if not callback.message:
        await callback.answer()
        return

    data = await state.get_data()
    schedule_date = data.get("schedule_date")
    tours = data.get("tours", [])

    if not schedule_date or not tours:
        await callback.message.answer("❌ Ошибка состояния.")
        await callback.answer()
        return

    tour_date = date.fromisoformat(schedule_date)

    # То же форматирование, что видят игроки
    player_view = build_player_schedule_message(tour_date, tours)
    message_text = "📋 ИТОГОВОЕ РАСПИСАНИЕ\n\n"
    message_text += player_view
    message_text += "\nТак это расписание увидят игроки.\n\nВыберите действие:"

    await callback.message.answer(
        message_text,
        reply_markup=get_final_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_edit_menu")
async def handle_back_to_edit_menu(callback: CallbackQuery, state: FSMContext):
    """Finish edit-past flow and return to schedule menu."""
    if not callback.message:
        await callback.answer()
        return

    await state.clear()
    await callback.message.answer(
        "✅ Редактирование расписания завершено. Выберите действие в меню «Расписание».",
    )
    await callback.answer()


@router.message(F.text == "✏️ Редактировать расписание")
async def start_edit_past(msg: Message, state: FSMContext):
    """Start edit-past flow: only for admin, ask for date ДД.ММ.ГГ to find day and edit."""
    if not msg.from_user:
        return
    if msg.from_user.id != bot_settings.admin_players:
        await msg.answer("Доступно только администратору.")
        return

    await state.clear()
    await state.set_state(ScheduleCreation.waiting_for_edit_date)
    await msg.answer(
        "✏️ Редактирование расписания\n\n"
        "Введите дату игрового дня в формате ДД.ММ.ГГ"
    )


@router.message(ScheduleCreation.waiting_for_edit_date)
async def process_edit_date(msg: Message, state: FSMContext):
    """Load schedule by date and show tour list for editing."""
    if not msg.text:
        await msg.answer("❌ Введите дату в формате ДД.ММ.ГГ")
        return

    parsed = parse_date_ddmmyy(msg.text)
    if not parsed:
        await msg.answer("❌ Неверный формат даты. Пример: 25.02.26")
        return

    date_tour = await get_date_tour_by_date(parsed)
    if not date_tour:
        await msg.answer("На эту дату нет расписания.")
        await state.clear()
        return

    db_tours = await get_tours_by_date_tour_id(date_tour.id)
    if not db_tours:
        await msg.answer("На эту дату нет туров.")
        await state.clear()
        return

    tours = [
        {
            "id": t.id,
            "time": t.time,
            "games": t.games,
            "teams_count": t.teams_count,
            "team_1_composition": t.team_1_composition or "",
            "team_2_composition": t.team_2_composition or "",
            "team_3_composition": t.team_3_composition,
        }
        for t in db_tours
    ]

    await state.update_data(
        date_tour_id=date_tour.id,
        schedule_date=parsed.isoformat(),
        tours=tours,
        edit_mode_from_db=True,
    )
    await state.set_state(None)

    tour_date = parsed
    await msg.answer(
        _format_tour_list_message(tour_date, tours, title="✏️ Редактирование расписания"),
        reply_markup=get_tour_list_keyboard(len(tours), from_db=True),
    )


@router.callback_query(F.data == "delete_schedule")
async def handle_delete_schedule(callback: CallbackQuery, state: FSMContext):
    """Delete schedule draft and cancel creation"""
    if not callback.message:
        await callback.answer()
        return

    await state.clear()
    await callback.message.answer(
        "🗑️ Расписание удалено.\n\n"
        "Создание расписания отменено."
    )
    await callback.answer()


@router.callback_query(F.data == "confirm_publish")
async def handle_confirm_publish(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Confirm and publish schedule - save to DB, notify players."""
    if not callback.message:
        await callback.answer()
        return

    data = await state.get_data()
    schedule_date = data.get("schedule_date")
    date_tour_id = data.get("date_tour_id")
    tours = data.get("tours", [])

    if not schedule_date or not tours or not date_tour_id:
        await callback.message.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        await callback.answer()
        return

    tour_date = date.fromisoformat(schedule_date)

    # Calculate stats
    total_games = sum(tour.get("games", 0) for tour in tours)

    try:
        await save_schedule_to_db(date_tour_id, tours)
    except Exception as e:
        await callback.message.answer(
            f"❌ Ошибка при сохранении в БД: {e}\n\n"
            f"Попробуйте ещё раз или обратитесь к разработчику."
        )
        await callback.answer()
        return

    await send_full_schedule_to_players(tour_date, tours, bot)

    await state.clear()

    # Show success message в запрошенном формате
    weekday_full = get_weekday_full(tour_date)
    day_month = get_date_day_month(tour_date)

    await callback.message.answer(
        "✅ РАСПИСАНИЕ ОПУБЛИКОВАНО!\n\n"
        f"Дата: {weekday_full}, {day_month} {tour_date:%Y}\n"
        "📊 Общая информация:\n"
        f"• Туров: {len(tours)}\n"
        f"• Всего игр: {total_games}\n"
        "✅ Данные успешно занесены в базу\n"
        "📩 Игроки получили уведомления"
    )
    await callback.answer()


@router.message(ScheduleCreation.waiting_for_team_3_composition)
async def process_team_3_composition(msg: Message, state: FSMContext):
    """Process team 3 composition with validation and show final confirmation"""
    if not msg.text:
        await msg.answer("❌ Введите состав команды")
        return

    composition_text = msg.text.strip()
    data = await state.get_data()
    games_count = data.get("games_count", 10)

    validation_result = await validate_team_composition(composition_text, games_count)

    if not validation_result["valid"]:
        await msg.answer(
            build_composition_error_message(validation_result),
            parse_mode="Markdown",
        )
        return

    # Build formatted composition from validation result
    formatted_composition = "\n".join(
        slot["display"] for slot in validation_result["slots"]
    )

    await state.update_data(team_3_composition=formatted_composition)

    data = await state.get_data()
    schedule_date = data.get("schedule_date")
    tour_time = data.get("tour_time")
    games_count = data.get("games_count")
    team_1_composition = data.get("team_1_composition", "")
    team_2_composition = data.get("team_2_composition", "")

    if not schedule_date or not tour_time or not games_count:
        await msg.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        return

    tour_date = date.fromisoformat(schedule_date)
    weekday = get_weekday_short(tour_date)

    await state.set_state(ScheduleCreation.waiting_for_confirm)

    await msg.answer(
        f"✅ Все команды введены!\n\n"
        f"📅 {weekday}, {tour_date:%d.%m.%Y} | ⏰ {tour_time}\n"
        f"🎮 {games_count} игр\n\n"
        f"Команда 1:\n{team_1_composition}\n\n"
        f"Команда 2:\n{team_2_composition}\n\n"
        f"Команда 3:\n{formatted_composition}\n\n"
        f"Выберите действие:",
        reply_markup=get_team3_confirm_keyboard()
    )
