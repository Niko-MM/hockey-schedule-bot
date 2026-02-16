from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from bot.states.schedule import ScheduleCreation
from bot.config import bot_settings
from db.crud import (
    create_tournament_day,
    get_tours_count,
    get_date_tour_by_id,
    get_date_tour_by_date,
    get_available_players,
    get_reserve_players,
)
from bot.keyboards.admin.players_select import get_single_player_select_keyboard
from bot.keyboards.admin.schedule import (
    get_schedule_keyboard,
    get_teams_complete_keyboard,
)
from bot.keyboards.admin.slot_actions import get_slot_actions_keyboard
from bot.utils.date_parser import (
    parse_date_ddmmyy,
    get_weekday_short,
    normalize_time_hhmm,
)
from aiogram.types import CallbackQuery
from datetime import date


router = Router(name="admin_schedule")


@router.message(F.text == "➕ Составить расписание")
async def start_schedule_creation(msg: Message, state: FSMContext):
    """Старт создания расписания: запросить дату турнира"""
    if not msg.from_user:
        return

    if msg.from_user.id != bot_settings.admin_players:
        return

    await state.clear()
    await state.set_state(ScheduleCreation.waiting_for_date)
    await msg.answer(
        "📅 Создание расписания.\n"
        "Введите дату турнира в формате ДД.ММ.ГГ"
    )


@router.message(ScheduleCreation.waiting_for_date)
async def process_date(msg: Message, state: FSMContext):
    """Parse date — allow any date, warn for past dates"""
    if not msg.text:
        await msg.answer("❌ Введите дату в формате ДД.ММ.ГГ")
        return

    parsed_date = parse_date_ddmmyy(msg.text)
    if not parsed_date:
        await msg.answer(
            "❌ Неверный формат даты.\nПример правильного формата: 25.02.26"
        )
        return

    today = date.today()

    # Soft warning for past dates (no blocking)
    if parsed_date < today:
        await msg.answer(
            f"⚠️ Внимание: вы создаёте расписание на ПРОШЕДШИЙ день ({parsed_date:%d.%m.%Y}).\n"
            f"Сегодня: {today:%d.%m.%Y}"
        )

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

    await state.update_data(date_tour_id=date_tour.id)
    await state.set_state(None)

    weekday = get_weekday_short(parsed_date)
    await msg.answer(
        f"📅 {weekday}, {parsed_date:%d.%m.%Y}\n\nВыберите действие:",
        reply_markup=get_schedule_keyboard(date_tour.id),
    )


@router.callback_query(F.data.startswith("add_tour:"))
async def handle_add_tour(callback: CallbackQuery, state: FSMContext):
    """Start adding a new tour (shift) to schedule with progress display"""
    if not callback.message:
        await callback.answer()
        return

    if not callback.data:
        await callback.answer()
        return

    if not callback.from_user or callback.from_user.id != bot_settings.admin_players:
        await callback.answer("🚫 Нет прав", show_alert=True)
        return

    try:
        date_tour_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    date_tour = await get_date_tour_by_id(date_tour_id)
    if not date_tour:
        await callback.answer("❌ Турнирный день не найден", show_alert=True)
        return

    tour_number = await get_tours_count(date_tour_id) + 1
    weekday = get_weekday_short(date_tour.date)

    await state.update_data(
        date_tour_id=date_tour_id,
        tour_number=tour_number,
        schedule_date=date_tour.date.isoformat(),
    )
    await state.set_state(ScheduleCreation.waiting_for_time)

    await callback.message.answer(
        f"📅 {weekday}, {date_tour.date:%d.%m.%Y}\n"
        f"🔢 Тур #{tour_number}\n\n"
        "⏰ Введите время тура (ЧЧ:ММ)\n"
        "Пример: 05:00"
    )
    await callback.answer()


@router.message(ScheduleCreation.waiting_for_time)
async def process_time(msg: Message, state: FSMContext):
    """Validate and normalize tour time, proceed to games count with progress display"""
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
    date_tour_id = data.get("date_tour_id")
    tour_number = data.get("tour_number", 1)
    schedule_date = data.get("schedule_date")

    if not date_tour_id or not schedule_date:
        await msg.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        return

    if not isinstance(schedule_date, str):
        await msg.answer("❌ Ошибка данных даты. Начните заново.")
        await state.clear()
        return

    tour_date = date.fromisoformat(schedule_date)
    weekday = get_weekday_short(tour_date)

    await state.update_data(tour_time=normalized_time)
    await state.set_state(ScheduleCreation.waiting_for_games)

    await msg.answer(
        f"📅 {weekday}, {tour_date:%d.%m.%Y}\n"
        f"🔢 Тур #{tour_number}\n"
        f"⏰ Время: {normalized_time}\n\n"
        "🎮 Введите количество игр в туре"
    )


@router.message(ScheduleCreation.waiting_for_games)
async def process_games(msg: Message, state: FSMContext):
    """Validate games count (1-20) and proceed to teams count"""
    if not msg.text:
        await msg.answer("❌ Введите количество игр (число от 1 до 20)")
        return

    try:
        games_count = int(msg.text.strip())
        if games_count < 1 or games_count > 20:
            raise ValueError
    except ValueError:
        await msg.answer(
            "❌ Неверное количество игр.\nВведите число от 1 до 20 (например: 5)"
        )
        return

    data = await state.get_data()
    date_tour_id = data.get("date_tour_id")
    tour_number = data.get("tour_number", 1)
    schedule_date = data.get("schedule_date")
    tour_time = data.get("tour_time")

    if not all([date_tour_id, schedule_date, tour_time]):
        await msg.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        return

    if not isinstance(schedule_date, str):
        await msg.answer("❌ Ошибка данных даты. Начните заново.")
        await state.clear()
        return

    tour_date = date.fromisoformat(schedule_date)
    weekday = get_weekday_short(tour_date)

    await state.update_data(games_count=games_count)
    await state.set_state(ScheduleCreation.waiting_for_teams)

    await msg.answer(
        f"📅 {weekday}, {tour_date:%d.%m.%Y}\n"
        f"🔢 Тур #{tour_number}\n"
        f"⏰ Время: {tour_time}\n"
        f"🎮 Игр: {games_count}\n\n"
        "👥 Введите количество команд в туре"
    )


@router.message(ScheduleCreation.waiting_for_teams)
async def process_teams(msg: Message, state: FSMContext):
    """Validate teams count (2 or 3) and start slot-based player selection"""
    if not msg.text:
        await msg.answer("❌ Введите количество команд (2 или 3)")
        return

    try:
        teams_count = int(msg.text.strip())
        if teams_count not in (2, 3):
            raise ValueError
    except ValueError:
        await msg.answer(
            "❌ Неверное количество команд.\nВведите 2 или 3 (например: 2)"
        )
        return

    data = await state.get_data()
    date_tour_id = data.get("date_tour_id")
    tour_number = data.get("tour_number", 1)
    schedule_date = data.get("schedule_date")
    tour_time = data.get("tour_time")
    games_count = data.get("games_count")

    if not all([date_tour_id, schedule_date, tour_time, games_count]):
        await msg.answer("❌ Ошибка состояния. Начните заново.")
        await state.clear()
        return

    if not isinstance(schedule_date, str):
        await msg.answer("❌ Ошибка данных даты. Начните заново.")
        await state.clear()
        return

    tour_date = date.fromisoformat(schedule_date)
    weekday = get_weekday_short(tour_date)

    # Determine slots per team
    slots_per_team = 4 if teams_count == 3 else 12

    # Init slot-based state
    await state.update_data(
        teams_count=teams_count,
        slots_per_team=slots_per_team,
        total_games=games_count,
        current_team=1,
        current_slot=1,
        slot_players=[],
        all_selected_players=set(),
        current_page=1,
        is_reserve_list=False,
    )
    await state.set_state(ScheduleCreation.waiting_for_players)

    # Get players from DB (sorted by Russian alphabet)
    available = await get_available_players()
    reserves = await get_reserve_players()
    all_players = available + reserves

    # Filter available players
    available_players = [p for p in all_players if p.id not in set()]

    # Paginate: 9 players per page (3x3 grid)
    players_per_page = 9
    total_pages = max(
        1, (len(available_players) + players_per_page - 1) // players_per_page
    )
    current_page = 1
    start_idx = (current_page - 1) * players_per_page
    end_idx = start_idx + players_per_page
    players_on_page = available_players[start_idx:end_idx]

    # Send keyboard with 3x3 grid
    keyboard = get_single_player_select_keyboard(
        players=players_on_page,
        all_players=all_players,
        current_team=1,
        players_selected=0,
        required_per_team=slots_per_team,
        page=current_page,
        total_pages=total_pages,
        is_reserve_list=False,
    )

    await msg.answer(
        f"📅 {weekday}, {tour_date:%d.%m.%Y}\n"
        f"🔢 Тур #{tour_number}\n"
        f"⏰ Время: {tour_time}\n"
        f"🎮 Игры: {games_count}\n"
        f"👥 Команды: {teams_count} ({slots_per_team} слотов)\n\n"
        f"✅ Выберите игрока для слота 1 (команда 1):",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("pick:"), ScheduleCreation.waiting_for_players)
async def handle_player_pick(callback: CallbackQuery, state: FSMContext):
    """Handle player selection for current slot"""
    if (
        not callback.message
        or not isinstance(callback.message, Message)
        or not callback
    ):
        await callback.answer("❌ Сообщение недоступно", show_alert=True)
        return

    if not callback.data:
        return
    

    # Parse player ID
    try:
        player_id = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    data = await state.get_data()
    current_team = data.get("current_team", 1)
    current_slot = data.get("current_slot", 1)
    total_games = data.get("total_games", 10)
    slot_players = data.get("slot_players", [])
    all_selected = data.get("all_selected_players", set())
    current_page = data.get("current_page", 1)
    is_reserve_list = data.get("is_reserve_list", False)

    # Prevent adding more than 4 players to a slot
    if len(slot_players) >= 4:
        await callback.answer("❌ Максимум 4 игрока в слоте", show_alert=True)
        return

    # Prevent duplicate selection
    if player_id in all_selected:
        await callback.answer("⚠️ Игрок уже выбран", show_alert=True)
        return

    # Add player to current slot (games=0 means not yet assigned)
    slot_players.append({"player_id": player_id, "games": 0})
    all_selected.add(player_id)

    # Get player name for feedback (temporary placeholder)
    player_name = f"Игрок #{player_id}"

    # Save progress
    await state.update_data(
        slot_players=slot_players,
        all_selected_players=all_selected,
        current_team=current_team,
        current_slot=current_slot,
        current_page=current_page,
        is_reserve_list=is_reserve_list,
    )

    # Show action keyboard: add substitute OR next slot
    keyboard = get_slot_actions_keyboard(
        player_name=player_name,
        current_slot=current_slot,
        games_assigned=0,
        total_games=total_games,
        has_substitutes=False,
    )

    await callback.message.answer(
        f"✅ {player_name} добавлен в слот {current_slot} (команда {current_team})\n\n"
        f"Выберите действие:",
        reply_markup=keyboard,
    )

    await callback.answer()


@router.callback_query(F.data.startswith("list:"), ScheduleCreation.waiting_for_players)
async def handle_list_switch(callback: CallbackQuery, state: FSMContext):
    """Switch between main and reserve players lists"""
    if not callback.message or not isinstance(callback.message, Message):
        await callback.answer("❌ Сообщение недоступно", show_alert=True)
        return

    if not callback.data:
        return

    # Parse list type
    list_type = callback.data.split(":")[1]
    is_reserve = list_type == "reserve"

    data = await state.get_data()
    current_team = data.get("current_team", 1)
    teams_count = data.get("teams_count", 2)
    players_in_team = data.get("players_in_team", [])
    all_selected = data.get("all_selected_players", set())
    current_page = data.get("current_page", 1)

    # Get players from DB
    available = await get_available_players()
    reserves = await get_reserve_players()
    all_players = available + reserves

    # Filter available players based on list type
    if is_reserve:
        players_pool = [p for p in reserves if p.id not in all_selected]
    else:
        players_pool = [p for p in available if p.id not in all_selected]

    # Paginate: 9 players per page (3x3 grid)
    players_per_page = 9
    total_pages = max(1, (len(players_pool) + players_per_page - 1) // players_per_page)
    current_page = min(current_page, total_pages)  # Keep within bounds

    start_idx = (current_page - 1) * players_per_page
    end_idx = start_idx + players_per_page
    players_on_page = players_pool[start_idx:end_idx]

    # Determine required players per team
    required_per_team = 4 if teams_count == 3 else 12

    # Update state
    await state.update_data(is_reserve_list=is_reserve, current_page=current_page)

    # Send updated keyboard
    keyboard = get_single_player_select_keyboard(
        players=players_on_page,
        all_players=all_players,
        current_team=current_team,
        players_selected=len(players_in_team),
        required_per_team=required_per_team,
        page=current_page,
        total_pages=total_pages,
        is_reserve_list=is_reserve,
    )

    list_name = "запасных" if is_reserve else "основных"
    await callback.message.answer(
        f"👥 Показаны {list_name} игроки:\n"
        f"Команда {current_team}: {len(players_in_team)}/{required_per_team}",
        reply_markup=keyboard,
    )

    # Delete previous message to avoid clutter (optional, safe version)
    try:
        if callback.message:
            await callback.message.delete()
    except Exception:
        pass

    await callback.answer()


@router.callback_query(F.data.startswith("page:"), ScheduleCreation.waiting_for_players)
async def handle_pagination(callback: CallbackQuery, state: FSMContext):
    """Handle pagination (prev/next page)"""
    if not callback.message or not isinstance(callback.message, Message):
        await callback.answer("❌ Сообщение недоступно", show_alert=True)
        return

    if not callback.data:
        return

    # Parse direction
    direction = callback.data.split(":")[1]
    if direction not in ("prev", "next"):
        await callback.answer()
        return

    data = await state.get_data()
    current_team = data.get("current_team", 1)
    teams_count = data.get("teams_count", 2)
    players_in_team = data.get("players_in_team", [])
    all_selected = data.get("all_selected_players", set())
    current_page = data.get("current_page", 1)
    is_reserve_list = data.get("is_reserve_list", False)

    # Get players from DB
    available = await get_available_players()
    reserves = await get_reserve_players()
    all_players = available + reserves

    # Filter available players based on current list type
    if is_reserve_list:
        players_pool = [p for p in reserves if p.id not in all_selected]
    else:
        players_pool = [p for p in available if p.id not in all_selected]

    # Paginate: 9 players per page (3x3 grid)
    players_per_page = 9
    total_pages = max(1, (len(players_pool) + players_per_page - 1) // players_per_page)

    # Update page number
    if direction == "prev" and current_page > 1:
        current_page -= 1
    elif direction == "next" and current_page < total_pages:
        current_page += 1
    else:
        await callback.answer("⚠️ Нельзя перейти дальше", show_alert=False)
        return

    start_idx = (current_page - 1) * players_per_page
    end_idx = start_idx + players_per_page
    players_on_page = players_pool[start_idx:end_idx]

    # Determine required players per team
    required_per_team = 4 if teams_count == 3 else 12

    # Update state
    await state.update_data(current_page=current_page)

    # Send updated keyboard
    keyboard = get_single_player_select_keyboard(
        players=players_on_page,
        all_players=all_players,
        current_team=current_team,
        players_selected=len(players_in_team),
        required_per_team=required_per_team,
        page=current_page,
        total_pages=total_pages,
        is_reserve_list=is_reserve_list,
    )

    await callback.message.answer(
        f"📄 Страница {current_page}/{total_pages}\n"
        f"Команда {current_team}: {len(players_in_team)}/{required_per_team}",
        reply_markup=keyboard,
    )

    # Delete previous message to avoid clutter (optional, safe version)
    try:
        if callback.message:
            await callback.message.delete()
    except Exception:
        pass

    await callback.answer()


@router.callback_query(F.data == "slot:next_slot", ScheduleCreation.waiting_for_players)
async def handle_next_slot(callback: CallbackQuery, state: FSMContext):
    """Complete current slot and finalize using shared logic"""
    if not callback.message or not isinstance(callback.message, Message):
        await callback.answer("❌ Сообщение недоступно", show_alert=True)
        return

    data = await state.get_data()
    total_games = data.get("total_games", 10)
    slot_players = data.get("slot_players", [])

    if not slot_players:
        await callback.answer("❌ Нет игроков в текущем слоте", show_alert=True)
        return

    # Calculate remaining games and assign to last player
    assigned_sum = sum(p["games"] for p in slot_players[:-1])
    remaining_games = total_games - assigned_sum

    if remaining_games < 0:
        await callback.answer("❌ Ошибка: сумма игр превышает лимит", show_alert=True)
        return

    # Assign remaining games to last player
    slot_players[-1]["games"] = remaining_games
    await state.update_data(slot_players=slot_players)

    # Delegate all complex logic to _finalize_slot
    await _finalize_slot(callback.message, state)
    await callback.answer()


@router.callback_query(
    F.data == "slot:add_substitute", ScheduleCreation.waiting_for_players
)
async def handle_add_substitute(callback: CallbackQuery, state: FSMContext):
    """Prompt admin to enter games count for last added player before selecting substitute"""
    if not callback.message or not isinstance(callback.message, Message):
        await callback.answer("❌ Сообщение недоступно", show_alert=True)
        return

    data = await state.get_data()
    slot_players = data.get("slot_players", [])
    total_games = data.get("total_games", 10)

    if not slot_players:
        await callback.answer("❌ Нет игроков в слоте", show_alert=True)
        return
    
    if len(slot_players) >= 4:
        await callback.answer("❌ Максимум 4 игрока в слоте", show_alert=True)
        return

    # Calculate already assigned games (excluding last player who has games=0)
    assigned_sum = sum(p["games"] for p in slot_players[:-1])
    remaining = total_games - assigned_sum

    if remaining <= 0:
        await callback.answer("❌ Все игры уже распределены", show_alert=True)
        return

    # Save context and switch to games input state
    await state.update_data(
        waiting_for_substitute=True  # Flag: next player will be substitute
    )
    await state.set_state(ScheduleCreation.waiting_for_games_in_slot)

    last_player_id = slot_players[-1]["player_id"]
    await callback.message.answer(
        f"🔢 Сколько игр сыграет Игрок #{last_player_id} до замены?\n"
        f"Доступно: {remaining} игр (максимум)"
    )

    await callback.answer()


@router.message(ScheduleCreation.waiting_for_games_in_slot)
async def handle_games_in_slot(msg: Message, state: FSMContext):
    """Handle input of games count for current player in slot"""
    if not msg.text:
        await msg.answer("❌ Введите число")
        return

    try:
        games_input = int(msg.text.strip())
        if games_input <= 0:
            raise ValueError
    except ValueError:
        await msg.answer("❌ Введите положительное число (например: 6)")
        return

    data = await state.get_data()
    slot_players = data.get("slot_players", [])
    total_games = data.get("total_games", 10)
    current_team = data.get("current_team", 1)
    current_slot = data.get("current_slot", 1)
    all_selected = data.get("all_selected_players", set())
    current_page = data.get("current_page", 1)
    is_reserve_list = data.get("is_reserve_list", False)

    if not slot_players:
        await msg.answer("❌ Ошибка: нет игроков в слоте")
        await state.set_state(ScheduleCreation.waiting_for_players)
        return

    # Calculate already assigned games (excluding last player who we are updating)
    assigned_sum = sum(p["games"] for p in slot_players[:-1])
    remaining_before = total_games - assigned_sum

    if games_input > remaining_before:
        await msg.answer(
            f"❌ Слишком много игр. Максимум: {remaining_before}\n"
            f"Повторите ввод:"
        )
        return

    # Update last player's games count
    slot_players[-1]["games"] = games_input
    remaining_after = total_games - (assigned_sum + games_input)

    # Save updated state
    await state.update_data(slot_players=slot_players)

    if remaining_after == 0:
        # Slot is complete — finalize it automatically
        await _finalize_slot(msg, state)
        return

    # Still games left — show player selection for substitute
    available = await get_available_players()
    reserves = await get_reserve_players()
    all_players = available + reserves
    available_players = [p for p in all_players if p.id not in all_selected]

    if not available_players:
        await msg.answer("❌ Нет доступных игроков для замены!")
        return

    # Paginate
    players_per_page = 9
    total_pages = max(1, (len(available_players) + players_per_page - 1) // players_per_page)
    start_idx = (current_page - 1) * players_per_page
    end_idx = start_idx + players_per_page
    players_on_page = available_players[start_idx:end_idx]

    keyboard = get_single_player_select_keyboard(
        players=players_on_page,
        all_players=all_players,
        current_team=current_team,
        players_selected=len(slot_players),
        required_per_team=data.get("slots_per_team", 4),
        page=current_page,
        total_pages=total_pages,
        is_reserve_list=is_reserve_list
    )

    await state.set_state(ScheduleCreation.waiting_for_players)
    await msg.answer(
        f"✅ Игроку #{slot_players[-1]['player_id']} назначено {games_input} игр\n"
        f"Осталось: {remaining_after} игр в слоте {current_slot}\n\n"
        f"🔄 Выберите замену для слота {current_slot} (команда {current_team}):",
        reply_markup=keyboard
    )

async def _finalize_slot(message: Message, state: FSMContext):
    """Helper: finalize current slot using FRESH data from state"""
    data = await state.get_data()  # ← Актуальные данные из состояния
    
    current_team = data.get("current_team", 1)
    current_slot = data.get("current_slot", 1)
    slots_per_team = data.get("slots_per_team", 4)
    slot_players = data.get("slot_players", [])
    all_selected = data.get("all_selected_players", set())
    teams_count = data.get("teams_count", 2)

    # Save completed slot
    team_slots = data.get("team_slots", {})
    team_slots_key = f"team_{current_team}"
    team_slots.setdefault(team_slots_key, []).append(slot_players.copy())

    # Check if team is complete
    team_complete = len(team_slots[team_slots_key]) >= slots_per_team

    if team_complete:
        next_team = current_team + 1
        next_slot = 1

        if next_team > teams_count:
            # All teams complete
            await state.update_data(
                team_slots=team_slots,
                current_team=current_team,
                current_slot=current_slot,
                slot_players=[],
                all_selected_players=all_selected
            )
            await message.answer(
                f"✅ Все {teams_count} команды заполнены!\n\n"
                f"Выберите действие:",
                reply_markup=get_teams_complete_keyboard(teams_count)
            )
            return
    else:
        next_team = current_team
        next_slot = current_slot + 1

    # Prepare for next slot
    await state.update_data(
        team_slots=team_slots,
        current_team=next_team,
        current_slot=next_slot,
        slot_players=[],
        all_selected_players=all_selected,
        current_page=1,
        is_reserve_list=False
    )

    # Get players for next slot
    available = await get_available_players()
    reserves = await get_reserve_players()
    all_players = available + reserves
    available_players = [p for p in all_players if p.id not in all_selected]

    if not available_players:
        await message.answer("❌ Нет доступных игроков для следующего слота!")
        return

    players_per_page = 9
    total_pages = max(1, (len(available_players) + players_per_page - 1) // players_per_page)
    players_on_page = available_players[:players_per_page]

    keyboard = get_single_player_select_keyboard(
        players=players_on_page,
        all_players=all_players,
        current_team=next_team,
        players_selected=0,
        required_per_team=slots_per_team,
        page=1,
        total_pages=total_pages,
        is_reserve_list=False
    )

    action = "команды" if team_complete else "слота"
    # DEBUG: Log slot composition
    slot_summary = " | ".join([f"Игрок#{p['player_id']}({p['games']})" for p in slot_players])
    print(f"DEBUG: Слот {current_slot} команды {current_team}: {slot_summary}")
    await message.answer(
        f"✅ Слот {current_slot} завершён (команда {current_team})\n\n"
        f"➡️ Выберите игрока для {action} {next_team if team_complete else next_slot}:",
        reply_markup=keyboard
    )