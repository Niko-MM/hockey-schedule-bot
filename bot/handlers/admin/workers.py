from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, BufferedInputFile

from bot.config import bot_settings
from bot.keyboards.admin.admin_player import get_personal_keyboard
from bot.keyboards.admin.admin_worker import (
    get_admin_worker_main_keyboard,
    get_worker_schedule_keyboard,
    get_worker_control_keyboard,
)
from bot.states.worker_schedule import WorkerScheduleEdit
from bot.utils.date_parser import parse_date_ddmmyy, get_weekday_full, get_date_day_month
from bot.utils.worker_schedule_parser import parse_worker_schedule_csv
from bot.utils.worker_schedule_resolver import resolve_worker_slots
from bot.handlers.user.salary import handle_salary, handle_ratings
from db.crud import (
    get_all_workers,
    save_worker_schedule_for_date,
    get_person_surnames_by_ids,
)
from bot.utils.worker_schedule_image import build_worker_schedule_image

import aiohttp
from datetime import date
import re


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


@router.message(F.text == "➕ Составить расписание")
async def worker_schedule_create_start(msg: Message, state: FSMContext):
    """Start worker schedule creation: ask for date."""
    if not _is_admin_worker(msg):
        return

    await state.clear()
    await state.set_state(WorkerScheduleEdit.waiting_for_date_create)
    await msg.answer(
        "📅 Создание расписания работников.\n"
        "Введите дату в формате ДД.ММ.ГГ"
    )


@router.message(WorkerScheduleEdit.waiting_for_date_create)
async def worker_schedule_create_process_date(msg: Message, state: FSMContext):
    """Parse date and load schedule from Google Sheet (create mode)."""
    if not _is_admin_worker(msg) or not msg.text:
        return

    tour_date = parse_date_ddmmyy(msg.text)
    if not tour_date:
        await msg.answer(
            "❌ Неверный формат даты.\nПример правильного формата: 25.02.26"
        )
        return

    await _load_and_save_worker_schedule(msg, state, tour_date, mode="create")


@router.message(F.text == "✏️ Редактировать расписание")
async def worker_schedule_edit_start(msg: Message, state: FSMContext):
    """Start worker schedule edit: ask for date."""
    if not _is_admin_worker(msg):
        return

    await state.clear()
    await state.set_state(WorkerScheduleEdit.waiting_for_date_edit)
    await msg.answer(
        "✏️ Редактирование расписания работников.\n"
        "Введите дату в формате ДД.ММ.ГГ"
    )


@router.message(WorkerScheduleEdit.waiting_for_date_edit)
async def worker_schedule_edit_process_date(msg: Message, state: FSMContext):
    """Parse date and load schedule from Google Sheet (edit mode)."""
    if not _is_admin_worker(msg) or not msg.text:
        return

    tour_date = parse_date_ddmmyy(msg.text)
    if not tour_date:
        await msg.answer(
            "❌ Неверный формат даты.\nПример правильного формата: 25.02.26"
        )
        return

    await _load_and_save_worker_schedule(msg, state, tour_date, mode="edit")


async def _load_and_save_worker_schedule(
    msg: Message,
    state: FSMContext,
    tour_date: date,
    mode: str,
) -> None:
    """Common flow: load CSV, parse, resolve workers, save to DB."""
    await state.clear()

    raw_url = bot_settings.worker_schedule_sheet_csv_url
    if not raw_url:
        await msg.answer(
            "❌ Не настроена ссылка на таблицу расписания работников.\n"
            "Добавьте WORKER_SCHEDULE_SHEET_CSV_URL в .env и перезапустите бота."
        )
        return

    url = _normalize_sheet_url(raw_url)

    # Load CSV
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await msg.answer(
                        f"❌ Не удалось загрузить таблицу (HTTP {resp.status}). "
                        "Попробуйте позже."
                    )
                    return
                csv_text = await resp.text()
    except Exception:
        await msg.answer("❌ Ошибка при загрузке таблицы. Попробуйте позже.")
        return

    # Parse CSV
    slots_raw, parse_errors = parse_worker_schedule_csv(csv_text)
    if parse_errors:
        text = "⚠️ Ошибки формата таблицы:\n\n" + "\n".join(parse_errors)
        await msg.answer(text)
        return

    if not slots_raw:
        await msg.answer("⚠️ В таблице не найдено ни одной строки расписания.")
        return

    # Resolve surnames to worker IDs
    slots_resolved, resolve_errors = await resolve_worker_slots(slots_raw)
    if resolve_errors:
        text = "⚠️ Ошибки сопоставления фамилий с работниками:\n\n" + "\n".join(
            resolve_errors
        )
        await msg.answer(text)
        return

    # Save to DB (non-break slots will be stored)
    await save_worker_schedule_for_date(tour_date, slots_resolved)

    # Build display slots (id -> surname) for image
    all_ids = []
    for s in slots_resolved:
        for key in ("operator_id", "camera_id", "camera_c_id", "commentator_id", "referee_id"):
            pid = s.get(key)
            if pid is not None:
                all_ids.append(pid)
    id_to_surname = await get_person_surnames_by_ids(all_ids)

    display_slots = []
    for s in slots_resolved:
        display_slots.append({
            "time_slot": s.get("time_slot") or "",
            "operator": id_to_surname.get(s.get("operator_id"), ""),
            "camera": id_to_surname.get(s.get("camera_id"), ""),
            "camera_c": id_to_surname.get(s.get("camera_c_id"), ""),
            "commentator": id_to_surname.get(s.get("commentator_id"), ""),
            "referee": id_to_surname.get(s.get("referee_id"), ""),
            "is_break": s.get("is_break", False),
        })

    try:
        png_bytes = build_worker_schedule_image(tour_date, display_slots)
        photo = BufferedInputFile(file=png_bytes, filename="schedule.png")
        await msg.answer_photo(
            photo=photo,
            caption=f"Расписание работников на {get_weekday_full(tour_date)}, {get_date_day_month(tour_date)}.",
        )
    except Exception:
        pass  # If image build fails, still send text below

    weekday_full = get_weekday_full(tour_date)
    day_month = get_date_day_month(tour_date)
    total_slots = sum(1 for s in slots_resolved if not s.get("is_break"))

    if mode == "create":
        prefix = "✅ Расписание работников создано"
    else:
        prefix = "✅ Расписание работников обновлено"

    await msg.answer(
        f"{prefix} на {weekday_full}, {day_month}.\n"
        f"Слотов: {total_slots}."
    )


def _normalize_sheet_url(raw_url: str) -> str:
    """
    Normalize Google Sheets URL:
    - If already export?format=csv -> return as is.
    - If it's an /edit URL -> convert to /export?format=csv&gid=...
    - Otherwise, best-effort fallback to /export?format=csv&gid=0.
    """
    url = raw_url.strip()
    if "export?format=csv" in url:
        return url

    # Try to extract spreadsheet id and gid from typical edit URL
    # Example: https://docs.google.com/spreadsheets/d/<ID>/edit#gid=0
    m = re.search(r"/spreadsheets/d/([^/]+)/", url)
    spreadsheet_id = m.group(1) if m else None

    gid_match = re.search(r"[?#]gid=(\d+)", url)
    gid = gid_match.group(1) if gid_match else "0"

    if spreadsheet_id:
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"

    # Fallback: just append export params
    if "/edit" in url:
        base = url.split("/edit", 1)[0]
    else:
        base = url.rstrip("/")
    return f"{base}/export?format=csv&gid={gid}"