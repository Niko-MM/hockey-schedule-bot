from db.models import Person


def format_player_name(person: Person, all_players: list[Person]) -> str:
    """
    Format player name for display.
    If surname is unique → "Петров"
    If duplicate surnames → "Петров И." / "Петров А."
    """
    surname_duplicates = [
        p for p in all_players
        if p.surname.lower() == person.surname.lower() and p.id != person.id
    ]
    
    if surname_duplicates:
        initial = person.name[0].upper() if person.name else "?"
        return f"{person.surname} {initial}."
    else:
        return person.surname