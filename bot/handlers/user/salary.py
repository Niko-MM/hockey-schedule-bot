"""Обработчики меню пользователя: зарплата и заглушки (штрафы, рейтинги, правила)."""
import logging
from aiogram import Router, F
from aiogram.types import Message

from db.models import Person
from db.crud import (
    get_person_by_telegram_id,
    get_player_total_games,
    get_worker_total_shifts,
    get_top_players_by_games_in_period,
    get_top_players_by_total_games,
    get_player_games_for_period,
    is_period_closed,
)
from bot.utils.periods import get_current_two_week_period, get_previous_two_week_period, get_today_kaliningrad


router = Router(name="user_salary")


def _fmt_rub(amount: int) -> str:
    """Форматирование суммы: пробел как разделитель тысяч."""
    return f"{amount:,}".replace(",", " ")


@router.message(F.text == "💰 Зарплата")
async def handle_salary(msg: Message):
    """
    Зарплата: по игрокам — по двухнедельным периодам (долг за прошлые 2 нед. + накопление),
    перенос последних 3 игр воскресенья 2-й недели; вратарь/работник — всего.
    """
    if not msg.from_user:
        return

    person = await get_person_by_telegram_id(msg.from_user.id)
    if not person:
        await msg.answer("Сначала пройдите регистрацию.")
        return

    if not (person.is_player or person.is_goalkeeper or person.is_worker):
        await msg.answer("Доступно только участникам лиги с назначенной ролью.")
        return

    lines = ["💰 Зарплата\n"]

    # Игрок: периодная логика
    amount_prev = 0
    games_cur = 0
    today = get_today_kaliningrad()
    prev_start, prev_end = None, None

    if person.is_player:
        period_start, period_end = get_current_two_week_period()
        prev_start, prev_end = get_previous_two_week_period()

        # Долг за прошлые 2 недели (если период закончился и ещё не закрыт расчётом)
        if today >= prev_end:
            prev_closed = await is_period_closed(prev_start)
            if not prev_closed:
                games_prev, _ = await get_player_games_for_period(person.id, prev_start, prev_end)
                amount_prev = games_prev * person.player_rate
                period_label = f"{prev_start.strftime('%d.%m')}–{prev_end.strftime('%d.%m')}"
                lines.append(f"📋 Заработанное за прошлые 2 недели ({period_label}): {_fmt_rub(amount_prev)} ₽")
                lines.append("")

        # Накопление за текущий период
        games_cur, transferred = await get_player_games_for_period(person.id, period_start, period_end)
        amount_cur = games_cur * person.player_rate
        period_label_cur = f"{period_start.strftime('%d.%m')}–{period_end.strftime('%d.%m')}"
        lines.append(f"📈 Накопление за текущий период ({period_label_cur}): {games_cur} игр — {_fmt_rub(amount_cur)} ₽")
        if transferred > 0:
            amount_trans = transferred * person.player_rate
            lines.append(f"↩️ Переносится на следующую выплату: {transferred} игр ({_fmt_rub(amount_trans)} ₽)")
        lines.append("")

    # Вратарь: всего (пока 0)
    if person.is_goalkeeper:
        lines.append("Вратарь: 0 игр — 0 ₽")
        lines.append("")

    # Работник: всего
    if person.is_worker:
        shifts = await get_worker_total_shifts(person.id)
        amount_w = shifts * person.worker_rate
        lines.append(f"Работник: {shifts} смен — {_fmt_rub(amount_w)} ₽")
        lines.append("")

    # Итого
    total = 0
    if person.is_player:
        total += games_cur * person.player_rate
        if prev_start is not None and today >= prev_end and not await is_period_closed(prev_start):
            total += amount_prev
    if person.is_worker:
        shifts = await get_worker_total_shifts(person.id)
        total += shifts * person.worker_rate
    lines.append(f"Итого в лиге: {_fmt_rub(total)} ₽")

    text = "\n".join(lines).strip()
    await msg.answer(text)


@router.message(F.text == "👮‍♂️ Штрафы")
async def handle_penalties_stub(msg: Message):
    """Заглушка: раздел штрафов в разработке."""
    await msg.answer("Тут будет информация о штрафах.")


def _format_top_players(
    rows: list[tuple[Person, int]], games_label: str = "игр"
) -> list[str]:
    """Форматирует список (Person, total) в строки «место. Фамилия — N игр» с учётом ничьих."""
    if not rows:
        return []
    lines = []
    place = 0
    last_total = None
    for person, total in rows:
        if total != last_total:
            place += 1
            last_total = total
        lines.append(f"{place}. {person.surname} — {total} {games_label}")
    return lines


def _get_current_period_fallback():
    """Запасной расчёт периода без zoneinfo (если на сервере нет tzdata)."""
    from datetime import date, timedelta
    today = date.today()
    weekday = today.weekday()
    anchor = today - timedelta(days=weekday)
    period_start = anchor
    period_end = anchor + timedelta(days=14)
    return period_start, period_end


def _get_previous_period_fallback():
    """Прошлые 2 недели (запасной расчёт без zoneinfo)."""
    from datetime import timedelta
    start, end = _get_current_period_fallback()
    prev_start = start - timedelta(days=14)
    prev_end = start
    return prev_start, prev_end


@router.message(F.text == "🏆 Рейтинги")
async def handle_ratings(msg: Message):
    """Рейтинги: топ за прошлые 2 недели, главный нарушитель (заглушка), легенды лиги."""
    try:
        try:
            period_start, period_end = get_previous_two_week_period()
        except Exception as e:
            logging.warning("get_previous_two_week_period failed, using fallback: %s", e)
            period_start, period_end = _get_previous_period_fallback()

        top_period = await get_top_players_by_games_in_period(
            period_start, period_end, limit=3
        )
        legends = await get_top_players_by_total_games(limit=3)

        period_str = f"{period_start.strftime('%d.%m')}–{period_end.strftime('%d.%m.%Y')}"
        block1_lines = [
            "🏆 Рейтинги",
            "",
            "📊 Топ по играм за прошлые 2 недели (" + period_str + ")",
        ]
        block1_lines.extend(_format_top_players(top_period) or ["— нет данных —"])
        block1_lines.append("")

        block2_lines = [
            "👮‍♂️ Главный нарушитель",
            "Пока нет данных о штрафах.",
            "",
        ]

        block3_lines = [
            "🏅 Легенды лиги (всего игр)",
        ]
        block3_lines.extend(_format_top_players(legends) or ["— нет данных —"])

        text = "\n".join(block1_lines + block2_lines + block3_lines)
        await msg.answer(text)
    except Exception as e:
        logging.exception("handle_ratings failed")
        await msg.answer(
            "Не удалось загрузить рейтинги. Попробуйте позже или обратитесь к администратору."
        )


@router.message(F.text == "📜 Правила")
async def handle_rules_stub(msg: Message):
    """Заглушка: раздел правил в разработке."""
    await msg.answer("Тут будет информация о правилах.")
