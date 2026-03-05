from aiogram.fsm.state import State, StatesGroup


class UserScheduleView(StatesGroup):
    waiting_for_date = State()

