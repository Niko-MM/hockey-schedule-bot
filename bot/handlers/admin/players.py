from datetime import date, timedelta

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import bot_settings
from bot.handlers.user.salary import handle_salary, handle_ratings
from bot.keyboards.admin.admin_player import (
    get_admin_main_keyboard,
    get_control_keyboard,
    get_personal_keyboard,
    get_schedule_keyboard,
)
from bot.keyboards.admin.approval import get_first_role_keyboard
from db.crud import (
    get_pending_applications,
    get_all_players,
    close_salary_period,
    get_active_players_telegram_ids,
    is_period_closed,
    get_players_salary_report_for_period,
)
from bot.utils.periods import get_previous_two_week_period


router = Router(name="players")


def _is_admin_player(msg: Message) -> bool:
    return bool(msg.from_user) and msg.from_user.id == bot_settings.admin_players


@router.message(F.from_user.id == bot_settings.admin_players, F.text == "🔙  Назад")
async def admin_button_back(msg: Message):
    if not _is_admin_player(msg):
        return

    await msg.answer("Главное меню", reply_markup=await get_admin_main_keyboard())


@router.message(F.from_user.id == bot_settings.admin_players, F.text == "⚙️ Управление")
async def admin_control_button(msg: Message):
    if not _is_admin_player(msg):
        return

    await msg.answer("⚙️ Управление", reply_markup=await get_control_keyboard())


@router.message(F.from_user.id == bot_settings.admin_players, F.text == "👤 Личное")
async def admin_personal_button(msg: Message):
    if not _is_admin_player(msg):
        return

    await msg.answer("👤 Личное", reply_markup=await get_personal_keyboard())


@router.message(F.from_user.id == bot_settings.admin_players, F.text == "📋 Расписание")
async def admin_schedule_button(msg: Message):
    if not _is_admin_player(msg):
        return

    await msg.answer("📋 Расписание", reply_markup=await get_schedule_keyboard())


@router.message(F.from_user.id == bot_settings.admin_players, F.text == "👥 Игроки")
async def admin_players_list_button(msg: Message):
    """Список игроков лиги в алфавитном порядке."""
    if not _is_admin_player(msg):
        return

    players = await get_all_players()
    if not players:
        await msg.answer("👥 Игроки лиги\n\nПока никого нет в списке.")
        return

    header = f"👥 Игроки лиги ({len(players)})\n\n"
    lines = [f"{i}. {p.surname} {p.name}" for i, p in enumerate(players, 1)]
    text = header + "\n".join(lines)

    max_len = 4096
    if len(text) <= max_len:
        await msg.answer(text)
    else:
        await msg.answer(header)
        chunk = []
        chunk_len = 0
        for line in lines:
            if chunk_len + len(line) + 1 > max_len - 50:
                await msg.answer("\n".join(chunk))
                chunk = []
                chunk_len = 0
            chunk.append(line)
            chunk_len += len(line) + 1
        if chunk:
            await msg.answer("\n".join(chunk))


@router.message(F.from_user.id == bot_settings.admin_players, F.text == "📋 Заявки")
async def admin_applications_button(msg: Message, bot: Bot):
    """Показать список ожидающих заявок на вступление (из Управления)."""
    if not _is_admin_player(msg):
        return

    pending = await get_pending_applications()
    if not pending:
        await msg.answer("Нет ожидающих заявок.")
        return

    await msg.answer(f"📋 Заявки на вступление ({len(pending)}):")
    for p in pending:
        text = (
            f"🆕 Заявка\n\n👤 {p.surname} {p.name}\n@{p.username}"
            if p.username
            else f"🆕 Заявка\n\n👤 {p.surname} {p.name}"
        )
        await bot.send_message(
            msg.chat.id,
            text,
            reply_markup=get_first_role_keyboard(p.telegram_id),
        )


STUB_MESSAGE = "⏳ Этот раздел в разработке."


@router.message(F.from_user.id == bot_settings.admin_players, F.text == "✏️👤 Редактирование ролей")
@router.message(F.from_user.id == bot_settings.admin_players, F.text == "⚠️ Штрафы")
@router.message(F.from_user.id == bot_settings.admin_players, F.text == "⛔ Бан")
async def admin_control_stub(msg: Message):
    """Заглушки разделов Управления."""
    if not _is_admin_player(msg):
        return
    await msg.answer(STUB_MESSAGE)


def _salary_confirm_keyboard(period_start) -> InlineKeyboardMarkup:
    """Inline-кнопки подтверждения расчёта зарплаты за период."""
    period_iso = period_start.strftime("%Y-%m-%d")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=f"salary_confirm:{period_iso}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="salary_cancel"),
        ],
    ])


def _fmt_rub(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


@router.message(F.from_user.id == bot_settings.admin_players, F.text == "💰 Расчёт зарплаты")
async def admin_salary_calculation(msg: Message):
    """Предложить подтверждение: провести расчёт зарплаты игроков за предыдущий период."""
    if not _is_admin_player(msg):
        return

    prev_start, prev_end = get_previous_two_week_period()
    if await is_period_closed(prev_start):
        await msg.answer(
            f"Период {prev_start.strftime('%d.%m')}–{prev_end.strftime('%d.%m')} уже закрыт. "
            "Долг за него у игроков не отображается."
        )
        return

    period_label = f"{prev_start.strftime('%d.%m')}–{prev_end.strftime('%d.%m')}"
    await msg.answer(
        f"💰 Провести расчёт зарплаты **игроков** за период {period_label}?",
        reply_markup=_salary_confirm_keyboard(prev_start),
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("salary_confirm:"))
async def admin_salary_confirm(callback: CallbackQuery, bot: Bot):
    """Подтверждение расчёта: закрыть период, уведомить игроков, отправить отчёт админу."""
    if not callback.from_user or callback.from_user.id != bot_settings.admin_players:
        await callback.answer()
        return

    try:
        period_iso = callback.data.split(":", 1)[1]
        period_start = date.fromisoformat(period_iso)
    except (IndexError, ValueError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    period_end = period_start + timedelta(days=14)
    period_label = f"{period_start.strftime('%d.%m')}–{period_end.strftime('%d.%m')}"

    if await is_period_closed(period_start):
        if callback.message and isinstance(callback.message, Message):
            await callback.message.edit_text(f"Период {period_label} уже был закрыт.")
        await callback.answer()
        return

    await close_salary_period(period_start)

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"✅ Расчёт проведён. Период {period_label} закрыт. Игрокам отправлено уведомление."
        )

    report = await get_players_salary_report_for_period(period_start, period_end)
    for person, games, amount in report:
        if games == 0:
            continue
        try:
            text = (
                f"💰 Расчёт произведён за период {period_label}.\n\n"
                f"Вы сыграли {games} матчей и заработали {_fmt_rub(amount)} ₽."
            )
            await bot.send_message(chat_id=person.telegram_id, text=text)
        except Exception:
            pass

    report_lines = [f"📋 Зарплата игроков за период {period_label}\n", "Фамилия — игры — сумма"]
    involved = [(p, g, a) for p, g, a in report if g > 0]
    for person, games, amount in involved:
        report_lines.append(f"{person.surname} — {games} — {_fmt_rub(amount)} ₽")
    if not involved:
        report_lines.append("— в периоде не было задействованных игроков —")
    report_text = "\n".join(report_lines)

    if callback.message and callback.message.chat:
        await bot.send_message(callback.message.chat.id, report_text)
    await callback.answer()


@router.callback_query(F.data == "salary_cancel")
async def admin_salary_cancel(callback: CallbackQuery):
    """Отмена расчёта зарплаты."""
    if not callback.from_user or callback.from_user.id != bot_settings.admin_players:
        await callback.answer()
        return
    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text("❌ Расчёт отменён.")
    await callback.answer()


@router.message(F.from_user.id == bot_settings.admin_players, F.text == "👷 Расписание работников")
@router.message(F.from_user.id == bot_settings.admin_players, F.text == "👽 Расписание вратарей")
async def admin_schedule_stub(msg: Message):
    """Заглушки разделов расписания работников и вратарей."""
    if not _is_admin_player(msg):
        return
    await msg.answer(STUB_MESSAGE)


@router.message(F.from_user.id == bot_settings.admin_players, F.text == "💰 Моя зарплата")
async def admin_my_salary(msg: Message):
    """Админ смотрит свою зарплату так же, как обычный пользователь."""
    if not _is_admin_player(msg):
        return

    await handle_salary(msg)


@router.message(F.from_user.id == bot_settings.admin_players, F.text == "🏆 Рейтинги")
async def admin_my_ratings(msg: Message):
    """Админ смотрит рейтинги так же, как обычный пользователь."""
    if not _is_admin_player(msg):
        return

    await handle_ratings(msg)
