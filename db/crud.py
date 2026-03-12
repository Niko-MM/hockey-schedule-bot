from db.session import async_session_maker
from db.models import Person, Tour, PlayerTourStats, WorkerSchedule, SalaryPeriodClosed
from sqlalchemy import select, not_, delete, or_
from db.models import DateTour
from datetime import date, timedelta
from sqlalchemy import func
from typing import Any
import re


async def get_person_by_telegram_id(tg_id: int) -> Person | None:
    """Get person by telegram id"""
    async with async_session_maker() as session:
        stmt = select(Person).where(Person.telegram_id == tg_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def update_person_username(tg_id: int, username: str | None) -> None:
    """Update person's username (called on /start)"""
    async with async_session_maker() as session:
        stmt = select(Person).where(Person.telegram_id == tg_id)
        result = await session.execute(stmt)
        person = result.scalar_one_or_none()
        
        if person:
            person.username = username
            await session.commit()


async def get_person_username(person_id: int) -> str | None:
    """Get person's username by ID"""
    async with async_session_maker() as session:
        stmt = select(Person).where(Person.id == person_id)
        result = await session.execute(stmt)
        person = result.scalar_one_or_none()
        
        if person and person.username:
            return person.username
        return None


async def get_person_display_name(person_id: int) -> str:
    """Get display name for person (username or surname)"""
    async with async_session_maker() as session:
        stmt = select(Person).where(Person.id == person_id)
        result = await session.execute(stmt)
        person = result.scalar_one_or_none()
        
        if person:
            if person.username:
                return f"@{person.username}"
            else:
                return f"{person.surname} {person.name[0]}."
        return "Неизвестный"


async def get_person_by_id(person_id: int) -> Person | None:
    """Get person by primary key id"""
    async with async_session_maker() as session:
        stmt = select(Person).where(Person.id == person_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def get_person_surnames_by_ids(person_ids: list[int]) -> dict[int, str]:
    """Get id -> surname for given person ids (for worker schedule image labels)."""
    ids = [i for i in person_ids if i is not None]
    if not ids:
        return {}
    async with async_session_maker() as session:
        stmt = select(Person.id, Person.surname).where(Person.id.in_(ids))
        result = await session.execute(stmt)
        return {row[0]: row[1] or "" for row in result.all()}


async def get_pending_applications() -> list[Person]:
    """Список заявок на вступление: не активные, не забаненные. По id (порядок поступления)."""
    async with async_session_maker() as session:
        stmt = (
            select(Person)
            .where(Person.is_active.is_(False), Person.is_banned.is_(False))
            .order_by(Person.id)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def create_person(tg_id: int, surname: str, name: str, username: str | None = None) -> None:
    """creat person"""
    async with async_session_maker() as session:
        person = Person(
            telegram_id = tg_id,
            surname = surname,
            name = name,
            username = username,
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


async def get_all_players() -> list[Person]:
    """
    Все активные игроки лиги (is_active, is_player, не забанены).
    В алфавитном порядке по фамилии (А-Я, Ё → Е).
    """
    async with async_session_maker() as session:
        stmt = (
            select(Person)
            .where(
                Person.is_active,
                Person.is_player,
                not_(Person.is_banned),
            )
            .order_by(Person.surname)
        )
        result = await session.execute(stmt)
        players = list(result.scalars().all())
        return sorted(players, key=_russian_sort_key)


async def get_all_workers() -> list[Person]:
    """
    All active workers in the league (is_active, is_worker, not banned).
    Sorted by Russian alphabet (А-Я, Ё → Е).
    """
    async with async_session_maker() as session:
        stmt = (
            select(Person)
            .where(
                Person.is_active,
                Person.is_worker,
                not_(Person.is_banned),
            )
            .order_by(Person.surname)
        )
        result = await session.execute(stmt)
        workers = list(result.scalars().all())
        return sorted(workers, key=_russian_sort_key)


def _normalize_for_search(s: str) -> str:
    """Normalize string for search (lower, ё→е)."""
    return (s or "").strip().lower().replace("ё", "е")


async def get_all_persons_for_role_edit() -> list[Person]:
    """
    All persons for role editor list (not banned), sorted by surname.
    """
    async with async_session_maker() as session:
        stmt = (
            select(Person)
            .where(not_(Person.is_banned))
            .order_by(Person.surname, Person.name)
        )
        result = await session.execute(stmt)
        persons = list(result.scalars().all())
        return sorted(persons, key=_russian_sort_key)


async def search_persons_by_surname(
    surname: str,
    name_part: str | None = None,
) -> list[Person]:
    """
    Search persons by surname (and optional name part).
    Excludes banned. Returns list sorted by surname, name.
    """
    async with async_session_maker() as session:
        stmt = (
            select(Person)
            .where(not_(Person.is_banned))
            .order_by(Person.surname, Person.name)
        )
        result = await session.execute(stmt)
        all_persons = list(result.scalars().all())
    norm = _normalize_for_search(surname)
    if not norm:
        return []
    persons = [
        p
        for p in all_persons
        if _normalize_for_search(p.surname) == norm
    ]
    if name_part and persons:
        name_norm = _normalize_for_search(name_part)
        if name_norm:
            persons = [
                p
                for p in persons
                if (p.name or "").lower().replace("ё", "е").startswith(name_norm)
                or (len(name_norm) == 1 and p.name and p.name[0].lower().replace("ё", "е") == name_norm)
            ]
    return sorted(persons, key=_russian_sort_key)


async def update_person_roles(
    person_id: int,
    *,
    is_player: bool,
    is_worker: bool,
    is_goalkeeper: bool,
    is_officer: bool,
) -> None:
    """Set all role flags for a person."""
    async with async_session_maker() as session:
        stmt = select(Person).where(Person.id == person_id)
        result = await session.execute(stmt)
        person = result.scalar_one_or_none()
        if not person:
            return
        person.is_player = is_player
        person.is_worker = is_worker
        person.is_goalkeeper = is_goalkeeper
        person.is_officer = is_officer
        await session.commit()


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


async def get_active_players_telegram_ids() -> list[int]:
    """Telegram IDs of all active players (for notifications). Excludes banned."""
    async with async_session_maker() as session:
        stmt = (
            select(Person.telegram_id)
            .where(
                Person.is_active,
                Person.is_player,
                not_(Person.is_banned),
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
    

async def get_date_tour_by_date(tour_date: date) -> DateTour | None:
    """
    Get tournament day by exact date.
    Returns None if not found.
    """
    async with async_session_maker() as session:
        stmt = select(DateTour).where(DateTour.date == tour_date)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()


async def get_next_tour_date_for_players() -> date | None:
    """
    Get nearest tournament day for players (>= today) that has at least one tour.
    If there are no future days, return the last day with tours in the past.
    Used for user '📅 Расписание' (актуальный день/последний игровой день).
    """
    async with async_session_maker() as session:
        today = date.today()
        # Try to find the nearest day in the future (including today)
        stmt = (
            select(DateTour.date)
            .join(Tour, Tour.date_tour_id == DateTour.id)
            .where(DateTour.date >= today)
            .order_by(DateTour.date)
            .limit(1)
        )
        result = await session.execute(stmt)
        nearest_future = result.scalar_one_or_none()
        if nearest_future:
            return nearest_future

        # If there are no future days, show the last day with tours (for межсезонья/тестов)
        stmt_last = (
            select(DateTour.date)
            .join(Tour, Tour.date_tour_id == DateTour.id)
            .order_by(DateTour.date.desc())
            .limit(1)
        )
        result_last = await session.execute(stmt_last)
        return result_last.scalar_one_or_none()


async def get_last_schedule_dates(limit: int = 10) -> list[date]:
    """
    Последние даты с расписанием (по убыванию даты — самые свежие первые).
    Для подсказки пользователю при выборе даты.
    """
    async with async_session_maker() as session:
        stmt = (
            select(DateTour.date)
            .join(Tour, Tour.date_tour_id == DateTour.id)
            .order_by(DateTour.date.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [row[0] for row in result.all()]


async def save_worker_schedule_for_date(
    tour_date: date,
    slots: list[dict[str, Any]],
    *,
    is_published: bool = False,
) -> None:
    """
    Save worker schedule for a given date.

    - Get or create DateTour for tour_date.
    - Remove existing WorkerSchedule rows for this date *с тем же статусом публикации*
      (черновики отдельно от опубликованных).
    - Insert new rows for non-break slots in the order they are given.
    - 'camera_id' is stored as director_id, 'camera_c_id' as k_center_id.
    """
    async with async_session_maker() as session:
        # На лету добавляем колонку is_published, если её ещё нет в существующей БД (SQLite).
        # Это защищает от падений после обновления модели без отдельной миграции.
        try:
            from sqlalchemy import text

            await session.execute(text("PRAGMA table_info('worker_schedule')"))
            info = await session.execute(text("PRAGMA table_info('worker_schedule')"))
            columns = [row[1] for row in info.fetchall()]
            if "is_published" not in columns:
                await session.execute(
                    text(
                        "ALTER TABLE worker_schedule "
                        "ADD COLUMN is_published BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
                await session.commit()
        except Exception:
            # Если по какой-то причине не удалось проверить/создать колонку,
            # продолжаем — ошибка проявится ниже и будет видна в логах.
            pass
        # Get or create DateTour
        stmt_date = select(DateTour).where(DateTour.date == tour_date)
        result = await session.execute(stmt_date)
        date_tour = result.scalar_one_or_none()

        if not date_tour:
            date_tour = DateTour(date=tour_date)
            session.add(date_tour)
            await session.flush()

        # Remove existing worker schedule for this date with the same publication status
        await session.execute(
            delete(WorkerSchedule).where(
                WorkerSchedule.date_tour_id == date_tour.id,
                WorkerSchedule.is_published.is_(is_published),
            )
        )

        match_number = 0
        for slot in slots:
            if slot.get("is_break"):
                # Breaks are not stored in DB; only used for image
                continue

            match_number += 1

            ws = WorkerSchedule(
                date_tour_id=date_tour.id,
                match_number=match_number,
                time_slot=slot.get("time_slot") or "",
                operator_id=slot.get("operator_id"),
                director_id=slot.get("camera_id"),
                k_center_id=slot.get("camera_c_id"),
                commentator_id=slot.get("commentator_id"),
                referee_id=slot.get("referee_id"),
                is_published=is_published,
            )
            session.add(ws)

        await session.commit()


async def publish_worker_schedule_for_date(tour_date: date) -> int:
    """
    Переводит все черновые слоты расписания работников на дату в статус опубликованных.

    Возвращает количество опубликованных слотов.
    """
    async with async_session_maker() as session:
        stmt_date = select(DateTour).where(DateTour.date == tour_date)
        result = await session.execute(stmt_date)
        date_tour = result.scalar_one_or_none()
        if not date_tour:
            return 0

        stmt_ws = select(WorkerSchedule).where(
            WorkerSchedule.date_tour_id == date_tour.id,
            WorkerSchedule.is_published.is_(False),
        )
        result_ws = await session.execute(stmt_ws)
        drafts = list(result_ws.scalars().all())
        if not drafts:
            return 0

        for ws in drafts:
            ws.is_published = True

        await session.commit()
        return len(drafts)


async def delete_worker_schedule_draft_for_date(tour_date: date) -> int:
    """
    Удаляет все черновые слоты расписания работников на указанную дату.
    Возвращает количество удалённых строк.
    """
    async with async_session_maker() as session:
        stmt_date = select(DateTour).where(DateTour.date == tour_date)
        result = await session.execute(stmt_date)
        date_tour = result.scalar_one_or_none()
        if not date_tour:
            return 0

        result_del = await session.execute(
            delete(WorkerSchedule).where(
                WorkerSchedule.date_tour_id == date_tour.id,
                WorkerSchedule.is_published.is_(False),
            )
        )
        await session.commit()
        return result_del.rowcount or 0


async def get_active_workers_telegram_ids() -> list[int]:
    """
    Telegram IDs of all active workers (for notifications).
    Excludes banned and persons without telegram_id.
    """
    async with async_session_maker() as session:
        stmt = (
            select(Person.telegram_id)
            .where(
                Person.is_active,
                Person.is_worker,
                not_(Person.is_banned),
                Person.telegram_id.is_not(None),
            )
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def find_player_by_surname(
    surname: str, 
    initial: str | None = None
) -> Person | list[Person] | None:
    """
    Find player by surname and optional initial
    
    Returns:
    - Person (if one match)
    - list[Person] (if multiple matches)
    - None (if not found)
    """
    async with async_session_maker() as session:
        # Search by surname (case-insensitive)
        stmt = (
            select(Person)
            .where(
                Person.surname.ilike(surname),
                Person.is_active,
                Person.is_player
            )
            .order_by(Person.surname, Person.name)
        )
        result = await session.execute(stmt)
        players = list(result.scalars().all())
        
        if len(players) == 0:
            return None
        
        if len(players) == 1:
            return players[0]
        
        # Multiple players with same surname
        if initial:
            # Search by initial (first letter of name)
            matching = [
                p for p in players
                if p.name and p.name[0].upper() == initial.upper()
            ]
            if len(matching) == 1:
                # Exactly one match with initial - return it
                return matching[0]
            elif len(matching) > 1:
                # Multiple matches with same initial - return list
                return matching
            else:
                # No match with initial - return all players with this surname
                return players

        # Multiple players, initial not specified
        return players


async def find_similar_players(surname: str) -> list[Person]:
    """
    Find players with similar surnames (for suggestions)
    """
    async with async_session_maker() as session:
        stmt = (
            select(Person)
            .where(
                Person.surname.ilike(f"%{surname}%"),
                Person.is_active,
                Person.is_player
            )
            .order_by(Person.surname, Person.name)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


def parse_surname_from_composition(composition_text: str) -> list[str]:
    """
    Extract surnames from team composition text.
    Format: "Петров 6 / Иванов 4" or "Петров (К) 6"
    Returns list of surnames.
    """
    surnames = []
    lines = composition_text.strip().split('\n')
    
    for line in lines:
        # Split by / for substitutes
        players = line.split('/')
        for player_str in players:
            player_str = player_str.strip()
            if not player_str:
                continue
            
            # Remove captain marker
            player_str = re.sub(r'\([КкKk]\)', '', player_str).strip()
            
            # Extract surname (first word, possibly with initial)
            parts = player_str.split()
            if parts:
                surname_part = parts[0]
                # Remove trailing dot from initial if present
                surname = surname_part.rstrip('.')
                if surname:
                    surnames.append(surname)
    
    return surnames


def parse_player_games_from_composition(
    composition_text: str,
    total_games: int,
) -> dict[str, int]:
    """Parse player games from composition text.
    Format: "Петров 6 / Иванов 4" or "Петров (К) 6"
    Returns dict: {"Петров": 6, "Иванов": 4}
    """
    player_games = {}
    lines = composition_text.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Split by / for substitutes
        players = [p.strip() for p in line.split('/') if p.strip()]

        # Если один игрок в слоте и явного количества игр нет,
        # считаем, что он играет весь тур (total_games).
        single_player_slot = len(players) == 1

        for player_str in players:
            # Remove captain marker
            clean_str = re.sub(r'\([КкKk]\)', '', player_str).strip()

            parts = clean_str.split()
            if not parts:
                continue

            surname = parts[0].rstrip('.')
            games: int | None = None

            # Попробовать взять число игр из конца строки
            if len(parts) >= 2:
                try:
                    games = int(parts[-1])
                except ValueError:
                    games = None

            # Если игр нет и это одиночный слот — весь тур
            if games is None and single_player_slot:
                games = total_games

            # Если игр нет и это не одиночный слот — пропускаем
            if games is None:
                continue

            if surname in player_games:
                player_games[surname] += games
            else:
                player_games[surname] = games

    return player_games


async def create_tour_in_db(
    session,
    date_tour_id: int,
    time: str,
    games: int,
    teams_count: int,
    team_1_composition: str,
    team_2_composition: str,
    team_3_composition: str | None = None,
) -> Tour:
    """
    Create a tour in database using an existing session.
    (Сессия создаётся снаружи, чтобы избежать параллельных подключений к SQLite.)
    """
    tour = Tour(
        date_tour_id=date_tour_id,
        time=time,
        games=games,
        teams_count=teams_count,
        team_1_composition=team_1_composition,
        team_2_composition=team_2_composition,
        team_3_composition=team_3_composition,
    )
    session.add(tour)
    await session.flush()  # получить tour.id
    await session.refresh(tour)
    return tour


async def create_player_tour_stats(
    session,
    tour_id: int,
    player_id: int,
    games: int
) -> PlayerTourStats:
    """Create or update player tour stats"""
    # Check if already exists
    stmt = select(PlayerTourStats).where(
        PlayerTourStats.tour_id == tour_id,
        PlayerTourStats.player_id == player_id
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        existing.actual_games += games
        return existing
    else:
        stats = PlayerTourStats(
            tour_id=tour_id,
            player_id=player_id,
            actual_games=games
        )
        session.add(stats)
        return stats


async def save_schedule_to_db(
    date_tour_id: int,
    tours: list[dict]
) -> list[Tour]:
    """
    Save entire schedule to database.
    Returns list of created Tour objects.
    """
    async with async_session_maker() as session:
        created_tours = []

        for tour_data in tours:
            # Создаём тур в той же сессии
            tour = await create_tour_in_db(
                session=session,
                date_tour_id=date_tour_id,
                time=tour_data["time"],
                games=tour_data["games"],
                teams_count=tour_data["teams_count"],
                team_1_composition=tour_data["team_1_composition"],
                team_2_composition=tour_data["team_2_composition"],
                team_3_composition=tour_data.get("team_3_composition"),
            )
            created_tours.append(tour)

            # Parse and save player stats for each team
            for team_key in ["team_1_composition", "team_2_composition", "team_3_composition"]:
                composition = tour_data.get(team_key)
                if not composition:
                    continue

                # Parse player games from composition
                player_games = parse_player_games_from_composition(
                    composition,
                    total_games=tour_data["games"],
                )

                # Find players and create stats
                for surname, games in player_games.items():
                    # Find player by surname (get first match)
                    stmt = select(Person).where(
                        Person.surname.ilike(surname),
                        Person.is_active,
                        Person.is_player,
                    )
                    result = await session.execute(stmt)
                    player = result.scalars().first()

                    if player:
                        await create_player_tour_stats(
                            session,
                            tour.id,
                            player.id,
                            games=games,
                        )

        await session.commit()
        return created_tours


async def get_tours_by_date_tour_id(date_tour_id: int) -> list[Tour]:
    """Get all tours for a tournament day, ordered by time."""
    async with async_session_maker() as session:
        stmt = (
            select(Tour)
            .where(Tour.date_tour_id == date_tour_id)
            .order_by(Tour.time)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def update_tour(
    tour_id: int,
    time: str,
    games: int,
    teams_count: int,
    team_1_composition: str,
    team_2_composition: str,
    team_3_composition: str | None,
) -> Tour | None:
    """
    Update tour and recompute PlayerTourStats from compositions.
    Salary data stays in sync.
    """
    async with async_session_maker() as session:
        stmt = select(Tour).where(Tour.id == tour_id)
        result = await session.execute(stmt)
        tour = result.scalar_one_or_none()
        if not tour:
            return None

        tour.time = time
        tour.games = games
        tour.teams_count = teams_count
        tour.team_1_composition = team_1_composition
        tour.team_2_composition = team_2_composition
        tour.team_3_composition = team_3_composition

        await session.execute(
            delete(PlayerTourStats).where(PlayerTourStats.tour_id == tour_id)
        )

        tour_data = {
            "time": time,
            "games": games,
            "teams_count": teams_count,
            "team_1_composition": team_1_composition,
            "team_2_composition": team_2_composition,
            "team_3_composition": team_3_composition,
        }

        for team_key in [
            "team_1_composition",
            "team_2_composition",
            "team_3_composition",
        ]:
            composition = tour_data.get(team_key)
            if not composition:
                continue
            player_games = parse_player_games_from_composition(
                composition,
                total_games=games,
            )
            for surname, games_num in player_games.items():
                stmt = select(Person).where(
                    Person.surname.ilike(surname),
                    Person.is_active,
                    Person.is_player,
                )
                res = await session.execute(stmt)
                player = res.scalars().first()
                if player:
                    await create_player_tour_stats(
                        session, tour_id, player.id, games=games_num
                    )

        await session.commit()
        await session.refresh(tour)
        return tour


async def get_player_total_games(person_id: int) -> int:
    """Сумма actual_games по всем турам для персоны (роль игрок)."""
    async with async_session_maker() as session:
        stmt = select(func.coalesce(func.sum(PlayerTourStats.actual_games), 0)).where(
            PlayerTourStats.player_id == person_id
        )
        result = await session.execute(stmt)
        value = result.scalar()
        return int(value or 0)


async def get_worker_total_shifts(person_id: int) -> int:
    """Количество смен работника (число записей WorkerSchedule, где персона в любой роли)."""
    async with async_session_maker() as session:
        stmt = select(func.count(WorkerSchedule.id)).where(
            or_(
                WorkerSchedule.operator_id == person_id,
                WorkerSchedule.director_id == person_id,
                WorkerSchedule.k_center_id == person_id,
                WorkerSchedule.commentator_id == person_id,
                WorkerSchedule.referee_id == person_id,
            )
        )
        result = await session.execute(stmt)
        return int(result.scalar() or 0)


async def get_top_players_by_games_in_period(
    start_date: date,
    end_date: date,
    limit: int = 3,
) -> list[tuple[Person, int]]:
    """
    Топ игроков по сумме actual_games за период [start_date, end_date).
    Возвращает до limit мест с учётом ничьих: все с одинаковым числом игр,
    как у последнего в топе, тоже включаются.
    """
    async with async_session_maker() as session:
        subq = (
            select(
                PlayerTourStats.player_id,
                func.sum(PlayerTourStats.actual_games).label("total"),
            )
            .join(Tour, Tour.id == PlayerTourStats.tour_id)
            .join(DateTour, DateTour.id == Tour.date_tour_id)
            .where(DateTour.date >= start_date, DateTour.date < end_date)
            .group_by(PlayerTourStats.player_id)
        ).subquery()
        stmt = (
            select(subq.c.player_id, subq.c.total)
            .select_from(subq)
            .order_by(subq.c.total.desc())
        )
        result = await session.execute(stmt)
        rows = [(r.player_id, int(r.total)) for r in result.all()]

        if not rows:
            return []

        totals_seen = []
        chosen = []
        for pid, total in rows:
            if total not in totals_seen:
                totals_seen.append(total)
                if len(totals_seen) > limit:
                    break
            chosen.append((pid, total))

        if not chosen:
            return []

        ids = [c[0] for c in chosen]
        stmt_p = select(Person).where(Person.id.in_(ids))
        res_p = await session.execute(stmt_p)
        persons = {p.id: p for p in res_p.scalars().all()}
        return [(persons[pid], total) for pid, total in chosen if pid in persons]


async def get_top_players_by_total_games(
    limit: int = 3,
) -> list[tuple[Person, int]]:
    """
    Топ игроков по сумме actual_games за всё время (легенды лиги).
    До limit мест с учётом ничьих.
    """
    async with async_session_maker() as session:
        subq = (
            select(
                PlayerTourStats.player_id,
                func.sum(PlayerTourStats.actual_games).label("total"),
            )
            .group_by(PlayerTourStats.player_id)
        ).subquery()
        stmt = (
            select(subq.c.player_id, subq.c.total)
            .select_from(subq)
            .order_by(subq.c.total.desc())
        )
        result = await session.execute(stmt)
        rows = [(r.player_id, int(r.total)) for r in result.all()]

        if not rows:
            return []

        totals_seen = []
        chosen = []
        for pid, total in rows:
            if total not in totals_seen:
                totals_seen.append(total)
                if len(totals_seen) > limit:
                    break
            chosen.append((pid, total))

        if not chosen:
            return []

        ids = [c[0] for c in chosen]
        stmt_p = select(Person).where(Person.id.in_(ids))
        res_p = await session.execute(stmt_p)
        persons = {p.id: p for p in res_p.scalars().all()}
        return [(persons[pid], total) for pid, total in chosen if pid in persons]


# --- Зарплата по периодам и закрытые периоды ---

async def is_period_closed(period_start: date) -> bool:
    """Проверяет, закрыт ли период зарплаты (админ нажал «Расчёт»)."""
    async with async_session_maker() as session:
        stmt = select(SalaryPeriodClosed).where(SalaryPeriodClosed.period_start == period_start)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None


async def close_salary_period(period_start: date) -> None:
    """Закрыть период зарплаты (после расчёта админом)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    async with async_session_maker() as session:
        closed = SalaryPeriodClosed(
            period_start=period_start,
            closed_at=datetime.now(ZoneInfo("Europe/Kaliningrad")),
        )
        session.add(closed)
        await session.commit()


def _sunday_week2(period_start: date) -> date:
    """Воскресенье второй недели периода (день 13 от понедельника)."""
    return period_start + timedelta(days=13)


async def get_player_games_for_period(
    person_id: int,
    period_start: date,
    period_end: date,
) -> tuple[int, int]:
    """
    Игры игрока за период [period_start, period_end) для зарплаты.
    Правило: последние 3 игры последнего тура в воскресенье 2-й недели переносятся на следующую выплату.
    Возвращает (игр_в_период, перенесено_игр).
    """
    async with async_session_maker() as session:
        sunday_w2 = _sunday_week2(period_start)
        stmt = (
            select(PlayerTourStats.player_id, PlayerTourStats.actual_games, Tour.id, Tour.games, DateTour.date)
            .join(Tour, Tour.id == PlayerTourStats.tour_id)
            .join(DateTour, DateTour.id == Tour.date_tour_id)
            .where(
                DateTour.date >= period_start,
                DateTour.date < period_end,
                PlayerTourStats.player_id == person_id,
            )
        )
        result = await session.execute(stmt)
        rows = result.all()

        games_in_period = 0
        transferred_games = 0

        # Последний тур в воскресенье 2-й недели (по времени)
        stmt_last = (
            select(Tour.id, Tour.games)
            .join(DateTour, DateTour.id == Tour.date_tour_id)
            .where(DateTour.date == sunday_w2)
            .order_by(Tour.time.desc())
            .limit(1)
        )
        res_last = await session.execute(stmt_last)
        last_row = res_last.one_or_none()
        last_tour_id = last_row[0] if last_row else None
        last_tour_games = last_row[1] if last_row else 0

        for r in rows:
            tour_id, tour_date = r[2], r[4]
            ag = r[1]
            if tour_date == sunday_w2 and last_tour_id is not None and tour_id == last_tour_id:
                stmt_sum = select(func.sum(PlayerTourStats.actual_games)).where(PlayerTourStats.tour_id == tour_id)
                res_sum = await session.execute(stmt_sum)
                total_in_tour = int(res_sum.scalar() or 0)
                if total_in_tour > 0:
                    ratio = ag / total_in_tour
                    games_in_period += int(round((last_tour_games - 3) * ratio))
                    transferred_games += int(round(3 * ratio))
                else:
                    games_in_period += ag
            else:
                games_in_period += ag

        return (games_in_period, transferred_games)


async def get_players_salary_report_for_period(
    period_start: date,
    period_end: date,
) -> list[tuple[Person, int, int]]:
    """
    Список игроков с играми и суммой за период (для отчёта админу).
    Только активные игроки (is_player, не забанены). Сортировка по фамилии.
    Возвращает [(Person, игры_в_период, сумма), ...].
    """
    players = await get_all_players()
    report = []
    for p in players:
        games, _ = await get_player_games_for_period(p.id, period_start, period_end)
        amount = games * p.player_rate
        report.append((p, games, amount))
    return report
