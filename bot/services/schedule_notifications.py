"""
Schedule notifications for players:
- short change notice for tomorrow;
- full schedule broadcast on publish.
"""
from datetime import date, timedelta

from aiogram import Bot

from db.crud import get_active_players_telegram_ids
from bot.utils.date_parser import (
    get_weekday_short,
    get_weekday_full,
    get_date_day_month,
)


def _is_tomorrow(tour_date: date) -> bool:
    return tour_date == date.today() + timedelta(days=1)


async def notify_players_schedule_changed(tour_date: date, bot: Bot) -> None:
    """
    If tour_date is tomorrow, send a short notice to all active players.
    Use after editing existing schedule. Failures per user are ignored.
    """
    if not _is_tomorrow(tour_date):
        return

    telegram_ids = await get_active_players_telegram_ids()
    text = (
        f"📅 Изменения в расписании на завтра ({tour_date:%d.%m.%y}). "
        "Откройте раздел «Расписание» в боте для просмотра."
    )

    for chat_id in telegram_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except Exception:
            pass


def build_player_schedule_message(tour_date: date, tours: list[dict]) -> str:
    """Full schedule text for players (used on publish and in user view)."""
    weekday_full = get_weekday_full(tour_date)
    day_month = get_date_day_month(tour_date)
    msg = f"📅 РАСПИСАНИЕ ИГР\n🗓 {weekday_full}, {day_month}\n\n"

    for i, tour in enumerate(tours, 1):
        msg += f"🔢 ТУР #{i}\n"
        msg += f"⏰ {tour['time']}\n"
        msg += f"{tour['games']} игр\n\n"
        parts = [tour["team_1_composition"], tour["team_2_composition"]]
        if tour.get("team_3_composition"):
            parts.append(tour["team_3_composition"])
        msg += "\n\n".join(parts)
        msg += "\n────────────────────"
        if i < len(tours):
            msg += "\n\n"

    return msg


async def send_full_schedule_to_players(
    tour_date: date,
    tours: list[dict],
    bot: Bot,
) -> None:
    """Broadcast full schedule for a day to all active players."""
    telegram_ids = await get_active_players_telegram_ids()
    if not telegram_ids:
        return

    text = build_player_schedule_message(tour_date, tours)

    for chat_id in telegram_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except Exception:
            # Ignore per-user errors (invalid chat, blocked bot, etc.)
            pass
