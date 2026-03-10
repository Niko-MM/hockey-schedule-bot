"""Role editor: list all persons, search by surname, toggle roles, save."""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.config import bot_settings
from bot.states.roles import RoleEdit
from bot.keyboards.admin.roles import (
    get_roles_editor_keyboard,
    ROLE_KEYS,
    ROLE_LABELS,
)
from db.crud import (
    get_all_persons_for_role_edit,
    search_persons_by_surname,
    get_person_by_id,
    update_person_roles,
)


router = Router(name="admin_roles")


def _is_role_admin(msg: Message | CallbackQuery) -> bool:
    user = msg.from_user if msg.from_user else None
    if not user:
        return False
    return user.id in (bot_settings.admin_players, bot_settings.admin_worker)


def _person_roles_line(person) -> str:
    parts = []
    if person.is_player:
        parts.append(ROLE_LABELS["player"])
    if person.is_worker:
        parts.append(ROLE_LABELS["worker"])
    if person.is_goalkeeper:
        parts.append(ROLE_LABELS["goalkeeper"])
    if person.is_officer:
        parts.append(ROLE_LABELS["officer"])
    return "  " + (", ".join(parts) if parts else "— нет ролей")


def _build_list_message(persons: list) -> str:
    lines = ["✏️👤 Редактирование ролей\n"]
    for p in persons:
        lines.append(f"{p.surname} {p.name}")
        lines.append(_person_roles_line(p))
        lines.append("")
    lines.append("Введите фамилию или ФИО пользователя для редактирования ролей.")
    return "\n".join(lines).strip()


def _roles_from_person(person) -> dict[str, bool]:
    return {
        "player": person.is_player,
        "worker": person.is_worker,
        "goalkeeper": person.is_goalkeeper,
        "officer": person.is_officer,
    }


def _roles_display(roles: dict[str, bool]) -> str:
    parts = [ROLE_LABELS[k] for k in ROLE_KEYS if roles.get(k)]
    return ", ".join(parts) if parts else "— нет ролей"


@router.message(
    F.text == "✏️👤 Редактирование ролей",
)
async def start_edit_roles(msg: Message, state: FSMContext):
    """Show list of all persons and their roles, then wait for surname."""
    if not _is_role_admin(msg):
        return

    await state.clear()
    persons = await get_all_persons_for_role_edit()
    if not persons:
        await msg.answer("✏️👤 Редактирование ролей\n\nВ базе пока нет ни одной персоны.")
        return

    text = _build_list_message(persons)
    if len(text) > 4096:
        chunk1 = text[:4000].rsplit("\n", 1)[0]
        await msg.answer(chunk1)
        await msg.answer(
            text[len(chunk1) :].strip()
            or "Введите фамилию или ФИО пользователя для редактирования ролей."
        )
    else:
        await msg.answer(text)

    await state.set_state(RoleEdit.waiting_for_person_query)


@router.message(RoleEdit.waiting_for_person_query, F.text)
async def process_person_query(msg: Message, state: FSMContext):
    """Handle surname (or surname + name) input: search and open editor or ask to choose."""
    if not _is_role_admin(msg) or not msg.text:
        return

    parts = msg.text.strip().split(maxsplit=1)
    surname = parts[0]
    name_part = parts[1] if len(parts) > 1 else None

    persons = await search_persons_by_surname(surname, name_part)

    if not persons:
        await msg.answer(
            "Никого не найдено. Введите фамилию или Фамилия Имя (например: Иванов Иван)."
        )
        return

    if len(persons) == 1:
        await _open_editor(msg, state, persons[0])
        return

    lines = ["Найдено несколько человек:\n"]
    for i, p in enumerate(persons, 1):
        lines.append(f"{i}. {p.surname} {p.name} ({_roles_display(_roles_from_person(p))})")
    lines.append("\nВведите номер строки для выбора.")
    await msg.answer("\n".join(lines))
    await state.update_data(person_ids=[p.id for p in persons])
    await state.set_state(RoleEdit.waiting_for_person_choice)


@router.message(RoleEdit.waiting_for_person_choice, F.text)
async def process_person_choice(msg: Message, state: FSMContext):
    """Handle number choice when multiple persons match."""
    if not _is_role_admin(msg) or not msg.text:
        return

    data = await state.get_data()
    person_ids = data.get("person_ids") or []
    if not person_ids:
        await state.clear()
        await msg.answer("Сессия истекла. Нажмите «✏️👤 Редактирование ролей» снова.")
        return

    try:
        n = int(msg.text.strip())
    except ValueError:
        await msg.answer("Введите номер из списка (число).")
        return

    if n < 1 or n > len(person_ids):
        await msg.answer(f"Введите число от 1 до {len(person_ids)}.")
        return

    person_id = person_ids[n - 1]
    person = await get_person_by_id(person_id)
    if not person:
        await msg.answer("Ошибка: персона не найдена.")
        await state.clear()
        return

    await _open_editor(msg, state, person)


async def _open_editor(msg: Message, state: FSMContext, person) -> None:
    """Send inline role editor for one person and store state."""
    roles = _roles_from_person(person)
    await state.update_data(person_id=person.id, roles=roles)
    await state.set_state(RoleEdit.waiting_for_person_query)

    text = (
        f"👤 {person.surname} {person.name}\n\n"
        f"Роли: {_roles_display(roles)}\n\n"
        "Нажимайте на роль, чтобы включить или выключить, затем «Сохранить»."
    )
    await msg.answer(
        text,
        reply_markup=get_roles_editor_keyboard(person.id, roles),
    )


@router.callback_query(F.data.startswith("role_toggle:"))
async def callback_role_toggle(callback: CallbackQuery, state: FSMContext):
    """Toggle one role in editor; update message and state."""
    if not _is_role_admin(callback):
        await callback.answer()
        return

    try:
        _, person_id_str, role_key = callback.data.split(":", 2)
        person_id = int(person_id_str)
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    if role_key not in ROLE_KEYS:
        await callback.answer()
        return

    data = await state.get_data()
    if data.get("person_id") != person_id:
        await callback.answer("Редактируйте текущего человека или введите фамилию заново.", show_alert=True)
        return

    roles = dict(data.get("roles") or {})
    for k in ROLE_KEYS:
        roles.setdefault(k, False)
    roles[role_key] = not roles[role_key]
    await state.update_data(roles=roles)

    person = await get_person_by_id(person_id)
    name_line = f"{person.surname} {person.name}" if person else ""

    text = (
        f"👤 {name_line}\n\n"
        f"Роли: {_roles_display(roles)}\n\n"
        "Нажимайте на роль, чтобы включить или выключить, затем «Сохранить»."
    )
    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            text,
            reply_markup=get_roles_editor_keyboard(person_id, roles),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("role_save:"))
async def callback_role_save(callback: CallbackQuery, state: FSMContext):
    """Save roles to DB and finish editor."""
    if not _is_role_admin(callback):
        await callback.answer()
        return

    try:
        _, person_id_str = callback.data.split(":", 1)
        person_id = int(person_id_str)
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    data = await state.get_data()
    if data.get("person_id") != person_id:
        await callback.answer("Сессия не совпадает.", show_alert=True)
        return

    roles = data.get("roles") or {}
    await update_person_roles(
        person_id,
        is_player=roles.get("player", False),
        is_worker=roles.get("worker", False),
        is_goalkeeper=roles.get("goalkeeper", False),
        is_officer=roles.get("officer", False),
    )

    person = await get_person_by_id(person_id)
    name_line = f"{person.surname} {person.name}" if person else ""
    result_roles = _roles_display(roles)

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"✅ Роли обновлены.\n\n👤 {name_line}\nРоли: {result_roles}"
        )
    await state.clear()
    await callback.answer()
