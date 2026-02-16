from aiogram.fsm.state import State, StatesGroup



class ScheduleCreation(StatesGroup):
    waiting_for_date = State()      # Date input DD.MM.YY
    waiting_for_time = State()      # Tour time HH:MM
    waiting_for_games = State()     # Number of games (1-20)
    waiting_for_teams = State()     # Number of teams (2 or 3)
    
    # Player selection with slot/rotation support
    waiting_for_players = State()   # Selecting players for slots
    waiting_for_games_in_slot = State()  # Entering game count for current player in slot
    
    waiting_for_captains = State()  # Captain selection (2 teams only)
    waiting_for_confirm = State()   # Final schedule confirmation
