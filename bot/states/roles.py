from aiogram.fsm.state import StatesGroup, State


class RoleEdit(StatesGroup):
    waiting_for_person_query = State()
    waiting_for_person_choice = State()
