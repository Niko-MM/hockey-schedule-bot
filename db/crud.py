from db.session import async_session_maker
from db.models import Person
from sqlalchemy import select, not_
from db.models import DateTour
from datetime import date
from sqlalchemy import func
from db.models import Tour


async def get_person_by_telegram_id(tg_id: int) -> Person | None:
    """Get person by telegram id"""
    async with async_session_maker() as session:
        stmt = select(Person).where(Person.telegram_id == tg_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def create_person(tg_id: int, surname: str, name: str) -> None:
    """creat person"""
    async with async_session_maker() as session:
        person = Person(
            telegram_id = tg_id,
            surname = surname,
            name = name,
            is_active=False,
            is_banned=False,   
            is_player=False,
            is_goalkeeper=False,
            is_worker=False,
            is_officer=False
        )
        session.add(person)
        await session.commit()


async def approve_person(tg_id: int, role: str) -> Person | None:
    """
    approve person.
    Save in db
    """
    async with async_session_maker() as session:
        stmt = select(Person).where(Person.telegram_id == tg_id)
        result = await session.execute(stmt)
        person = result.scalar_one_or_none()
        
        if not person:
            return None

        person.is_player = False
        person.is_goalkeeper = False
        person.is_worker = False
        person.is_officer = False
        
        if role == "player":
            person.is_player = True
        elif role == "worker":
            person.is_worker = True
        elif role == "goalkeeper":
            person.is_goalkeeper = True
        elif role == "officer": 
            person.is_officer = True
        
        person.is_active = True
        await session.commit()
        await session.refresh(person)
        
        return person
    

async def add_second_role(tg_id: int, role: str) -> Person | None:
    """add second role without resetting first one"""
    async with async_session_maker() as session:
        stmt = select(Person).where(Person.telegram_id == tg_id)
        result = await session.execute(stmt)
        person = result.scalar_one_or_none()
        
        if not person:
            return None

        if role == "player":
            person.is_player = True
        elif role == "worker":
            person.is_worker = True
        elif role == "goalkeeper":
            person.is_goalkeeper = True
        
        await session.commit()
        await session.refresh(person)
        return person
    

async def reject_person(tg_id: int) -> Person | None:
    """reject application (ban player)"""
    async with async_session_maker() as session:
        stmt = select(Person).where(Person.telegram_id == tg_id)
        result = await session.execute(stmt)
        person = result.scalar_one_or_none()
        
        if not person:
            return None

        person.is_banned = True
        await session.commit()
        await session.refresh(person)
        return person
    

async def create_tournament_day(tour_date: date) -> DateTour:
    """Create tournament day record"""
    async with async_session_maker() as session:
        new_date = DateTour(date=tour_date)
        session.add(new_date)
        try:
            await session.commit()
            await session.refresh(new_date)
            return new_date
        except Exception:
            await session.rollback()
            raise ValueError(f"Расписание на {tour_date:%d.%m.%Y} уже существует")
        

async def get_tours_count(date_tour_id: int) -> int:
    """
    Get number of tours already added to this tournament day.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(func.count(Tour.id)).where(Tour.date_tour_id == date_tour_id)
        )
        return result.scalar_one() or 0
    

async def get_date_tour_by_id(date_tour_id: int) -> DateTour | None:
    """
    Get tournament day by ID.
    """
    async with async_session_maker() as session:
        stmt = select(DateTour).where(DateTour.id == date_tour_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    


def _russian_sort_key(person: Person) -> str:
    """
    Sort key for Russian alphabet.
    Replaces 'ё' with 'е' to place Ё after Е (ГОСТ 7.79-2000).
    """
    surname = person.surname or ""
    return surname.lower().replace('ё', 'е')


async def get_available_players() -> list[Person]:
    """
    Get active players available for regular games (is_available=True).
    Sorted by Russian alphabet (А-Я, Ё → Е).
    """
    async with async_session_maker() as session:
        stmt = (
            select(Person)
            .where(
                Person.is_active,
                Person.is_player,
                Person.is_available 
            )
            .order_by(Person.surname)
        )
        result = await session.execute(stmt)
        players = list(result.scalars().all())
        return sorted(players, key=_russian_sort_key)


async def get_reserve_players() -> list[Person]:
    """
    Get active reserve players (is_available=False).
    Sorted by Russian alphabet (А-Я, Ё → Е).
    """
    async with async_session_maker() as session:
        stmt = (
            select(Person)
            .where(
                Person.is_active,
                Person.is_player,
                not_(Person.is_available)
            )
            .order_by(Person.surname)
        )
        result = await session.execute(stmt)
        players = list(result.scalars().all())
        return sorted(players, key=_russian_sort_key)
    

async def get_date_tour_by_date(tour_date: date) -> DateTour | None:
    """
    Get tournament day by exact date.
    Returns None if not found.
    """
    async with async_session_maker() as session:
        stmt = select(DateTour).where(DateTour.date == tour_date)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    

