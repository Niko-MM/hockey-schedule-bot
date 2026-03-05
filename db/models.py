from db.session import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, DateTime, Date as SaDate
from datetime import date as Date, datetime


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(nullable=True)  # Telegram username (без @)
    surname: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=False)
    is_banned: Mapped[bool] = mapped_column(default=False)
    is_available: Mapped[bool] = mapped_column(default=True)

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
    teams_count: Mapped[int] = mapped_column(nullable=False, default=2)

    team_1_composition: Mapped[str | None] = mapped_column(nullable=True)
    team_2_composition: Mapped[str | None] = mapped_column(nullable=True)
    team_3_composition: Mapped[str | None] = mapped_column(nullable=True)


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


class SalaryPeriodClosed(Base):
    """Закрытый период зарплаты: после «Расчёт» админом долг за этот период не показывается."""
    __tablename__ = "salary_period_closed"

    period_start: Mapped[Date] = mapped_column(SaDate(), primary_key=True)
    closed_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)