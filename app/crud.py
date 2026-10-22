"""Database query helpers for the API routers."""

from collections.abc import Sequence
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Binder, Card
from app.schemas import BinderCreate, BinderUpdate

SortOrder = Literal["asc", "desc"]
BinderOrderBy = Literal["name", "created_at"]


def escape_like(value: str) -> str:
    """Escape LIKE wildcards in user input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def contains(value: str) -> str:
    """Wrap already escaped user input into a LIKE contains pattern."""
    return f"%{escape_like(value)}%"


def get_binder(session: Session, binder_id: int) -> Binder | None:
    """Return the binder with the given id, or None."""
    return session.get(Binder, binder_id)


def get_binder_with_cards(session: Session, binder_id: int) -> Binder | None:
    """Return the binder with eagerly loaded cards (and certificates), or None."""
    stmt = (
        select(Binder)
        .where(Binder.id == binder_id)
        .options(selectinload(Binder.cards).selectinload(Card.certificate))
    )
    return session.scalars(stmt).first()


def list_binders(
    session: Session,
    *,
    name: str | None,
    order_by: BinderOrderBy | None,
    order: SortOrder,
    limit: int,
    offset: int,
) -> Sequence[Binder]:
    """List binders with optional name filter, ordering and pagination."""
    stmt = select(Binder)
    if name is not None:
        stmt = stmt.where(Binder.name.ilike(contains(name), escape="\\"))
    if order_by is None:
        stmt = stmt.order_by(Binder.id.desc() if order == "desc" else Binder.id.asc())
    elif order_by == "name":
        stmt = stmt.order_by(
            Binder.name.desc() if order == "desc" else Binder.name.asc(),
            Binder.id.asc(),
        )
    else:
        stmt = stmt.order_by(
            Binder.created_at.desc() if order == "desc" else Binder.created_at.asc(),
            Binder.id.asc(),
        )
    return session.scalars(stmt.limit(limit).offset(offset)).all()


def create_binder(session: Session, data: BinderCreate) -> Binder:
    """Persist a new binder."""
    binder = Binder(**data.model_dump(exclude_unset=True))
    session.add(binder)
    session.commit()
    session.refresh(binder)
    return binder


def update_binder(session: Session, binder: Binder, data: BinderUpdate) -> Binder:
    """Apply a partial update to a binder."""
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(binder, key, value)
    session.commit()
    session.refresh(binder)
    return binder


def delete_binder(session: Session, binder: Binder) -> None:
    """Delete a binder; the database cascades to cards and certificates."""
    session.delete(binder)
    session.commit()
