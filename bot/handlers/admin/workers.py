from aiogram import Router, F
from aiogram.types import Message

from bot.config import bot_settings
from bot.keyboards.admin.admin_player import get_personal_keyboard
from bot.keyboards.admin.admin_worker import (
    get_admin_worker_main_keyboard,
    get_worker_schedule_keyboard,
    get_worker_control_keyboard,
)
from bot.handlers.user.salary import handle_salary, handle_ratings
from db.crud import get_all_workers


router = Router(name="workers_admin")


def _is_admin_worker(msg: Message) -> bool:
    return bool(msg.from_user) and msg.from_user.id == bot_settings.admin_worker


@router.message(F.from_user.id == bot_settings.admin_worker, F.text == "🔙  Назад")
async def admin_worker_back(msg: Message):
    """Back to worker admin main menu."""
    await msg.answer("Главное меню", reply_markup=await get_admin_worker_main_keyboard())


@router.message(F.from_user.id == bot_settings.admin_worker, F.text == "📋 Расписание")
async def admin_worker_schedule_button(msg: Message):
    """Worker admin: open schedule submenu."""
    await msg.answer("📋 Расписание", reply_markup=await get_worker_schedule_keyboard())


@router.message(F.from_user.id == bot_settings.admin_worker, F.text == "⚙️ Управление")
async def admin_worker_control_button(msg: Message):
    """Worker admin: open control submenu (applications, roles, salary)."""
    await msg.answer("⚙️ Управление", reply_markup=await get_worker_control_keyboard())


@router.message(F.text == "👷 Работники")
async def admin_workers_list_button(msg: Message):
    """List workers in the league (no numbering)."""
    if not _is_admin_worker(msg):
        return

    workers = await get_all_workers()
    if not workers:
        await msg.answer("👷 Работники лиги\n\nПока никого нет в списке.")
        return

    header = f"👷 Работники лиги ({len(workers)})\n\n"
    # Without numbering, just "Фамилия Имя" per line
    lines = [f"{p.surname} {p.name}" for p in workers]
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


@router.message(F.text == "👤 Личное")
async def admin_worker_personal_button(msg: Message):
    """Show personal menu for worker admin (shared with other admins)."""
    if not _is_admin_worker(msg):
        return

    await msg.answer("👤 Личное", reply_markup=await get_personal_keyboard())


@router.message(F.text == "💰 Моя зарплата")
async def admin_worker_my_salary(msg: Message):
    """Worker admin checks own salary same as regular user."""
    if not _is_admin_worker(msg):
        return

    await handle_salary(msg)


@router.message(F.text == "🏆 Рейтинги")
async def admin_worker_my_ratings(msg: Message):
    """Worker admin checks ratings same as regular user."""
    if not _is_admin_worker(msg):
        return

    await handle_ratings(msg)