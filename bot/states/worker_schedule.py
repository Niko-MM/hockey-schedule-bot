from aiogram.fsm.state import StatesGroup, State


class WorkerScheduleEdit(StatesGroup):
    waiting_for_date_create = State()
    waiting_for_date_edit = State()

