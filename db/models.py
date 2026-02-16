from db.session import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from datetime import date as Date


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    surname: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=False)
    is_banned: Mapped[bool] = mapped_column(default=False)
    is_available: Mapped[bool] = mapped_column(default=True)

    #team
    team_number: Mapped[int] = mapped_column(default=1)
    is_captain: Mapped[bool] = mapped_column(default=False)
    player_order: Mapped[int] = mapped_column(default=0) 

    # Role
    is_player: Mapped[bool] = mapped_column(default=False)
    is_goalkeeper: Mapped[bool] = mapped_column(default=False)
    is_worker: Mapped[bool] = mapped_column(default=False)
    is_officer: Mapped[bool] = mapped_column(default=False)

    # Salary
    player_rate: Mapped[int] = mapped_column(default=580)
    goalkeeper_rate: Mapped[int] = mapped_column(default=750)
    worker_rate: Mapped[int] = mapped_column(default=500)


class DateTour(Base):
    __tablename__ = "date_tours"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[Date] = mapped_column(nullable=False, unique=True)


class Tour(Base):
    __tablename__ = "tours"

    id: Mapped[int] = mapped_column(primary_key=True)
    time: Mapped[str] = mapped_column(nullable=False)
    games: Mapped[int] = mapped_column(nullable=False)
    date_tour_id: Mapped[int] = mapped_column(ForeignKey("date_tours.id"))


class PlayerTourStats(Base):
    __tablename__ = "player_tour_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    tour_id: Mapped[int] = mapped_column(ForeignKey("tours.id"))
    actual_games: Mapped[int] = mapped_column(nullable=False)


class WorkerSchedule(Base):
    __tablename__ = "worker_schedule"

    id: Mapped[int] = mapped_column(primary_key=True)
    date_tour_id: Mapped[int] = mapped_column(ForeignKey("date_tours.id"))
    match_number: Mapped[int] = mapped_column(nullable=False)  # 1..27
    time_slot: Mapped[str] = mapped_column(nullable=False)     # "05:00-05:40"
    
    # Separate columns for each role
    operator_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    director_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    k_center_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    commentator_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    referee_id: Mapped[int] = mapped_column(ForeignKey("person.id"))