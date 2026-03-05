import asyncio

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from db.crud import (
    get_person_by_telegram_id,
      add_second_role,
      reject_person
)
from bot.keyboards.admin.approval import (
    get_save_or_add_keyboard,
    get_second_role_keyboard,
    get_first_role_keyboard,
)
from db.crud import approve_person
from bot.config import bot_settings
from bot.keyboards.user.main import get_user_keyboard
from bot.keyboards.user.wallpaper import get_wallpaper_offer_keyboard


ROLE_TEXT = {
    "player": "Игрок",
    "worker": "Работник",
    "goalkeeper": "Вратарь",
    "officer": "Офицер" 
}


router = Router(name="admin_approval")

# Track users who already got menu after wallpaper offer (avoid duplicate)
_menu_sent_after_wallpaper: set[int] = set()


async def _send_menu_after_delay(bot: Bot, tg_id: int, delay: float = 3.0) -> None:
    """Send main menu after delay; skip if already sent (e.g. user clicked Skip)."""
    await asyncio.sleep(delay)
    if tg_id in _menu_sent_after_wallpaper:
        return
    try:
        await bot.send_message(
            chat_id=tg_id,
            text="👇 Выберите действие:",
            reply_markup=get_user_keyboard(),
        )
        _menu_sent_after_wallpaper.add(tg_id)
    except Exception:
        pass


def is_admin(user_id: int) -> bool:
    """check if user has full rights to approve applications"""
    return user_id == bot_settings.admin_players or user_id == bot_settings.admin_worker


@router.callback_query(F.data.startswith("select_role:"))
async def handle_first_role_selection(callback: CallbackQuery):
    """first role choosed. Show save or add second role (no db save yet)"""


    if not callback.data:
        await callback.answer()
        return
    
    if not is_admin(callback.from_user.id):
        return

    try:
        _, tg_id_str, role = callback.data.split(":")
        tg_id = int(tg_id_str)
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    person = await get_person_by_telegram_id(tg_id=tg_id)
    if not person:
        await callback.answer("❌ Игрок не найден", show_alert=True)
        return

    role_ru = ROLE_TEXT.get(role, role)

    text = f"✅ {person.surname} {person.name}\nРоль: {role_ru}"

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=text, reply_markup=get_save_or_add_keyboard(tg_id, role)
        )

    await callback.answer()


@router.callback_query(F.data.startswith("add_second_role:"))
async def handle_add_second_role(callback: CallbackQuery):
    """show second role selection (exclude already selected role)"""
    if not callback.data:
        await callback.answer()
        return
    
    if not is_admin(callback.from_user.id):
        return

    try:
        _, tg_id_str, first_role = callback.data.split(":")
        tg_id = int(tg_id_str)
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    person = await get_person_by_telegram_id(tg_id=tg_id)
    if not person:
        await callback.answer("❌ Игрок не найден", show_alert=True)
        return

    role_ru = ROLE_TEXT.get(first_role, first_role)

    text = f"✅ {person.surname} {person.name}\nРоль: {role_ru}"

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=text, reply_markup=get_second_role_keyboard(tg_id, first_role)
        )

    await callback.answer()


@router.callback_query(F.data.startswith("back_to_first:"))
async def handle_back_to_first(callback: CallbackQuery):
    """return to first role selection state"""
    if not callback.data:
        await callback.answer()
        return
    
    if not is_admin(callback.from_user.id):
        return

    try:
        _, tg_id_str = callback.data.split(":")
        tg_id = int(tg_id_str)
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    person = await get_person_by_telegram_id(tg_id=tg_id)
    if not person:
        await callback.answer("❌ Игрок не найден", show_alert=True)
        return

    text = f"🆕 {person.surname} {person.name}\nОжидает роль"

    if callback.message and isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=text, reply_markup=get_first_role_keyboard(tg_id)
        )

    await callback.answer()


@router.callback_query(F.data.startswith("save:"))
async def handle_save(callback: CallbackQuery, bot: Bot):
    """save role(s) to db (1 or 2 roles)"""
    if not callback.data:
        await callback.answer()
        return
    
    if not is_admin(callback.from_user.id):
        return

    try:
        parts = callback.data.split(":")
        tg_id = int(parts[1])
        role1 = parts[2]
        role2 = parts[3] if len(parts) > 3 else None
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    person = await approve_person(tg_id, role1)
    if not person:
        await callback.answer("❌ Игрок не найден", show_alert=True)
        return

    if role2:
        person = await add_second_role(tg_id, role2)
        if not person:
            await callback.answer("❌ Ошибка добавления второй роли", show_alert=True)
            return

    # Send only welcome + wallpaper offer; menu comes on Skip or after delay
    try:
        role1_text = ROLE_TEXT.get(role1, role1)
        if role2:
            role2_text = ROLE_TEXT.get(role2, role2)
            roles_text = f"{role1_text}, {role2_text}"
        else:
            roles_text = role1_text

        welcome_text = (
            f"✅ Добро пожаловать, {person.name}!\n"
            f"Ваша роль: {roles_text}\n\n"
            "Установить фон чата с ботом?\n\n"
            "💡 Чтобы оставить фон только здесь: примени его, а затем верни свои старые обои "
            "в любой другой переписке.В боте всё останется."
        )
        await bot.send_message(
            chat_id=tg_id,
            text=welcome_text,
            reply_markup=get_wallpaper_offer_keyboard(),
        )
        asyncio.create_task(_send_menu_after_delay(bot, tg_id))
    except Exception:
        pass

    # Редактируем сообщение админа
    if callback.message and isinstance(callback.message, Message):
        role1_text = ROLE_TEXT.get(role1, role1)
        if role2:
            role2_text = ROLE_TEXT.get(role2, role2)
            text = f"✅ {person.surname} {person.name}\nРоли: {role1_text}, {role2_text}"
        else:
            text = f"✅ {person.surname} {person.name}\nРоль: {role1_text}"
        
        await callback.message.edit_text(text)

    await callback.answer("✅ Сохранено")


@router.callback_query(F.data == "skip_wallpaper")
async def handle_skip_wallpaper(callback: CallbackQuery, bot: Bot):
    """User skipped wallpaper — send menu and remove offer buttons."""
    if not callback.from_user:
        await callback.answer()
        return
    tg_id = callback.from_user.id

    if callback.message and isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(
                "Фон чата можно установить позже через меню.",
            )
        except Exception:
            pass

    try:
        await bot.send_message(
            chat_id=tg_id,
            text="👇 Выберите действие:",
            reply_markup=get_user_keyboard(),
        )
        _menu_sent_after_wallpaper.add(tg_id)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("reject:"))
async def handle_reject(callback: CallbackQuery, bot: Bot):
    """reject application (ban player)"""
    if not callback.data:
        await callback.answer()
        return
    
    if not is_admin(callback.from_user.id):
        return

    try:
        _, tg_id_str = callback.data.split(":")
        tg_id = int(tg_id_str)
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    person = await reject_person(tg_id)
    if not person:
        await callback.answer("❌ Игрок не найден", show_alert=True)
        return

    try:
        await bot.send_message(tg_id, "❌ Ваша заявка отклонена.")
    except Exception:
        pass

    if callback.message and isinstance(callback.message, Message):
        text = f"❌ {person.surname} {person.name} отклонён"
        await callback.message.edit_text(text)

    await callback.answer("❌ Отклонено")