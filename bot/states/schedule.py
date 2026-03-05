from aiogram.fsm.state import State, StatesGroup



class ScheduleCreation(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_games = State()
    waiting_for_team_1_composition = State()
    waiting_for_team_2_composition = State()
    waiting_for_team_3_composition = State()
    waiting_for_confirm = State()
    waiting_for_team_edit = State()
    # Edit existing schedule (draft or from DB)
    waiting_for_edit_date = State()
    waiting_for_edit_value = State()
