from aiogram.fsm.state import StatesGroup, State


class RegistrationPerson(StatesGroup):
    surname = State()
    name = State()
    confirm = State()