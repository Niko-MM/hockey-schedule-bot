from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from bot.states.registration import RegistrationPerson
from db.crud import get_person_by_telegram_id, create_person
from bot.keyboards.user.registration import get_confirm_keyboard
from bot.config import bot_settings
from bot.keyboards.admin.admin_player import get_admin_main_keyboard
from bot.keyboards.admin.approval import get_first_role_keyboard
from bot.keyboards.user.main import get_user_keyboard



router = Router(name="registration")


@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    """check person or registration"""

    if not msg.from_user:
        return
    
    if msg.from_user.id == bot_settings.admin_players:
        await msg.answer("👑 Панель администратора", reply_markup=await get_admin_main_keyboard())
        return 

    person = await get_person_by_telegram_id(msg.from_user.id)

    if person and person.is_banned:
        await msg.answer("Доступ заблокирован")
        return

    if person is None:
        await state.set_state(RegistrationPerson.surname)
        await msg.answer("Регистрация\nВведите вашу фамилию")
        return

    elif not person.is_active:
        await msg.answer("Ожидание подтверждения админа")
        return

    else:
        await msg.answer(f'Добро пожаловать, {person.name}!',
                         reply_markup=get_user_keyboard())


@router.message(RegistrationPerson.surname)
async def surname_person_input(msg: Message, state: FSMContext):
    """input surname and wait name person"""
    if not msg.text:
        await msg.answer("Введите вашу фамилию:")
        return

    surname = msg.text.strip().title()
    await state.update_data(surname=surname)
    await state.set_state(RegistrationPerson.name)
    await msg.answer("Введите ваше имя: ")


@router.message(RegistrationPerson.name)
async def name_person_input(msg: Message, state: FSMContext):
    """input name and wait confirm or fix"""
    if not msg.text:
        await msg.answer("Введите ваше имя")
        return

    name = msg.text.strip().title()
    await state.update_data(name=name)
    await state.set_state(RegistrationPerson.confirm)
    data = await state.get_data()
    surname = data["surname"]
    await msg.answer(
        f'Проверьте данные\n'
        f'Фамилия: {surname}\n'
        f'Имя: {name}',
        reply_markup=get_confirm_keyboard()
    )


@router.callback_query(F.data == "confirm")
async def confirm_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """registration confirmed → send to admins"""
    data = await state.get_data()
    
    surname = data.get("surname")
    name = data.get("name")
    
    if not surname or not name:
        await callback.answer("❌ Ошибка: данные регистрации утеряны", show_alert=True)
        await state.clear()
        if callback.message:
            await callback.message.answer("Пожалуйста, начните регистрацию заново командой /start")
        return

    tg_id = callback.from_user.id
    await create_person(tg_id=tg_id, surname=surname, name=name)
    
    admin_ids = [
        bot_settings.admin_players,
        bot_settings.admin_worker
    ]
    
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"🆕 Новая заявка на регистрацию\n\n👤 {surname} {name}",
                reply_markup=get_first_role_keyboard(tg_id)
            )
        except Exception:
            pass
    
    if callback.message:
        await callback.answer()
        await callback.message.answer("✅ Заявка отправлена. Ожидайте подтверждения администратора.")
        await state.clear()
