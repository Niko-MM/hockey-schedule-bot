"""
Двухнедельные периоды для рейтингов и зарплаты.
Отсчёт от якорного понедельника (ANCHOR_MONDAY в .env), часовой пояс — Калининград.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from bot.config import bot_settings


TZ = ZoneInfo("Europe/Kaliningrad")


def get_today_kaliningrad() -> date:
    """Текущая дата в Калининграде."""
    return datetime.now(TZ).date()


def _parse_anchor_monday() -> date | None:
    """Парсит anchor_monday из конфига (YYYY-MM-DD)."""
    raw = getattr(bot_settings, "anchor_monday", None)
    if not raw or not raw.strip():
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return None


def get_current_two_week_period() -> tuple[date, date]:
    """
    Возвращает текущее двухнедельное окно (start включительно, end исключительно).
    Окна: [anchor, anchor+14), [anchor+14, anchor+28), ...
    Если anchor_monday не задан — берётся понедельник текущей недели (Калининград).
    """
    today = get_today_kaliningrad()
    anchor = _parse_anchor_monday()

    if anchor is None:
        # Fallback: понедельник текущей недели (Калининград)
        weekday = today.weekday()  # 0 = понедельник
        anchor = today - timedelta(days=weekday)

    if anchor.weekday() != 0:
        # Сдвигаем на понедельник
        anchor = anchor - timedelta(days=anchor.weekday())

    days_since_anchor = (today - anchor).days
    if days_since_anchor < 0:
        # Сегодня раньше якоря — возвращаем первое окно
        period_index = 0
    else:
        period_index = days_since_anchor // 14

    period_start = anchor + timedelta(days=period_index * 14)
    period_end = period_start + timedelta(days=14)
    return (period_start, period_end)


def get_previous_two_week_period() -> tuple[date, date]:
    """Предыдущее двухнедельное окно (то, что только что закончилось)."""
    start, end = get_current_two_week_period()
    prev_start = start - timedelta(days=14)
    prev_end = start
    return (prev_start, prev_end)
