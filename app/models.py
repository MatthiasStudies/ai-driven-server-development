"""SQLAlchemy models mapping the schema defined in ``postgres-data/init.sql``."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Binder(Base):
    """A binder that physically stores cards (one side of the 1:N relation)."""

    __tablename__ = "binders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    cards: Mapped[list["Card"]] = relationship(
        back_populates="binder",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Card(Base):
    """A physical card stored in a binder."""

    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    binder_id: Mapped[int] = mapped_column(ForeignKey("binders.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    set_name: Mapped[str] = mapped_column(String(100))
    collector_number: Mapped[str] = mapped_column(String(20))
    rarity: Mapped[str] = mapped_column(String(50))
    variant: Mapped[str] = mapped_column(String(50), default="Standard")
    acquired_at: Mapped[date] = mapped_column(Date, default=date.today)

    binder: Mapped[Binder] = relationship(back_populates="cards")
    certificate: Mapped["GradingCertificate | None"] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class GradingCertificate(Base):
    """A grading certificate; strictly 1:1 with a card."""

    __tablename__ = "grading_certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(
        ForeignKey("cards.id", ondelete="CASCADE"), unique=True
    )
    grading_company: Mapped[str] = mapped_column(String(20))
    cert_number: Mapped[str] = mapped_column(String(50), unique=True)
    grade: Mapped[Decimal] = mapped_column(Numeric(3, 1))
    graded_at: Mapped[date] = mapped_column(Date)

    card: Mapped[Card] = relationship(back_populates="certificate")
