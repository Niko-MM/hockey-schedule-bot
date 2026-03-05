from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from db.crud import (
    get_person_by_telegram_id,
    get_next_tour_date_for_players,
    get_date_tour_by_date,
    get_tours_by_date_tour_id,
)
from bot.states.user_schedule import UserScheduleView
from bot.utils.date_parser import parse_date_ddmmyy, get_weekday_full, get_date_day_month
from bot.services.schedule_notifications import build_player_schedule_message


router = Router(name="user_schedule")


@router.message(F.text == "📅 Расписание")
async def handle_user_schedule(msg: Message, state: FSMContext):
    """Показать актуальное расписание для роли игрок."""
    if not msg.from_user:
        return

    person = await get_person_by_telegram_id(msg.from_user.id)
    if not person:
        await msg.answer("Сначала пройдите регистрацию.")
        return

    if not person.is_player:
        await msg.answer("Расписание пока доступно только для роли игрока.")
        return

    tour_date = await get_next_tour_date_for_players()
    if not tour_date:
        await msg.answer("Ближайших игровых дней пока нет.")
        return

    date_tour = await get_date_tour_by_date(tour_date)
    if not date_tour:
        await msg.answer("Ближайших игровых дней пока нет.")
        return

    db_tours = await get_tours_by_date_tour_id(date_tour.id)
    if not db_tours:
        await msg.answer("Ближайших игровых дней пока нет.")
        return

    tours = [
        {
            "time": t.time,
            "games": t.games,
            "teams_count": t.teams_count,
            "team_1_composition": t.team_1_composition or "",
            "team_2_composition": t.team_2_composition or "",
            "team_3_composition": t.team_3_composition,
        }
        for t in db_tours
    ]

    text = build_player_schedule_message(tour_date, tours)
    # Добавляем статус игрока в шапку
    weekday_full = get_weekday_full(tour_date)
    day_month = get_date_day_month(tour_date)
    header = f"📅 РАСПИСАНИЕ ИГР\nСтатус: Игрок\n🗓 {weekday_full}, {day_month}\n\n"
    # build_player_schedule_message уже содержит заголовок, поэтому используем только тело после первой пустой строки
    body = text.split("\n\n", 1)[1] if "\n\n" in text else text

    await msg.answer(
        header + body,
        reply_markup=None,
    )


@router.message(F.text == "📅 Выбрать дату")
async def start_pick_date(msg: Message, state: FSMContext):
    """Запросить у пользователя дату для просмотра расписания."""
    await state.set_state(UserScheduleView.waiting_for_date)
    await msg.answer("Введите дату игрового дня в формате ДД.ММ.ГГ")


@router.message(UserScheduleView.waiting_for_date)
async def handle_schedule_by_date(msg: Message, state: FSMContext):
    """Показать расписание на указанную дату для роли игрок."""
    if not msg.text:
        await msg.answer("❌ Введите дату в формате ДД.ММ.ГГ")
        return

    parsed = parse_date_ddmmyy(msg.text)
    if not parsed:
        await msg.answer("❌ Неверный формат даты. Пример: 25.02.26")
        return

    date_tour = await get_date_tour_by_date(parsed)
    if not date_tour:
        await msg.answer("На эту дату игр нет.")
        await state.clear()
        return

    db_tours = await get_tours_by_date_tour_id(date_tour.id)
    if not db_tours:
        await msg.answer("На эту дату игр нет.")
        await state.clear()
        return

    tours = [
        {
            "time": t.time,
            "games": t.games,
            "teams_count": t.teams_count,
            "team_1_composition": t.team_1_composition or "",
            "team_2_composition": t.team_2_composition or "",
            "team_3_composition": t.team_3_composition,
        }
        for t in db_tours
    ]

    text = build_player_schedule_message(parsed, tours)
    weekday_full = get_weekday_full(parsed)
    day_month = get_date_day_month(parsed)
    header = f"📅 РАСПИСАНИЕ ИГР\nСтатус: Игрок\n🗓 {weekday_full}, {day_month}\n\n"
    body = text.split("\n\n", 1)[1] if "\n\n" in text else text

    await msg.answer(header + body)
    await state.clear()

