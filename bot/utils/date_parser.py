from datetime import datetime, date
from typing import Optional


def parse_date_ddmmyy(date_str: str) -> Optional[date]:
    """
    Parse date string in DD.MM.YY or DD.MM.YYYY format.
    Returns date object or None if invalid.
    """
    date_str = date_str.strip()
    
    # Try DD.MM.YY (2-digit year)
    try:
        parsed = datetime.strptime(date_str, "%d.%m.%y")
        return parsed.date()
    except ValueError:
        pass
    
    # Try DD.MM.YYYY (4-digit year)
    try:
        parsed = datetime.strptime(date_str, "%d.%m.%Y")
        return parsed.date()
    except ValueError:
        pass
    
    return None


def normalize_time_hhmm(time_str: str) -> str | None:
    """
    Validate and normalize time string to HH:MM format (24-hour).
    Returns normalized string (e.g., "8:30" → "08:30") or None if invalid.
    """
    time_str = time_str.strip()
    parts = time_str.split(":")
    
    if len(parts) != 2:
        return None
    
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        
        if hours < 0 or hours > 23:
            return None
        if minutes < 0 or minutes > 59:
            return None
        
        return f"{hours:02d}:{minutes:02d}"
    except ValueError:
        return None
    

def get_weekday_short(date_obj: date) -> str:
    """
    Get short weekday name in Russian (Пн, Вт, Ср...).
    """
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    return weekdays[date_obj.weekday()]  # weekday(): 0=пн, 6=вс