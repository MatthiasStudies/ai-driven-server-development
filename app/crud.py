"""Database query helpers for the API routers."""

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Literal

from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.models import Binder, Card, GradingCertificate
from app.schemas import (
    BinderCreate,
    BinderUpdate,
    CardCreate,
    CardUpdate,
    CertificateCreate,
)

SortOrder = Literal["asc", "desc"]
BinderOrderBy = Literal["name", "created_at"]
CardOrderBy = Literal["name", "set_name", "rarity", "acquired_at"]
CertificateOrderBy = Literal["grade", "graded_at"]

CARD_ORDER_COLUMNS: Mapping[
    CardOrderBy, InstrumentedAttribute[str] | InstrumentedAttribute[date]
] = {
    "name": Card.name,
    "set_name": Card.set_name,
    "rarity": Card.rarity,
    "acquired_at": Card.acquired_at,
}


def escape_like(value: str) -> str:
    """Escape LIKE wildcards in user input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def contains(value: str) -> str:
    """Wrap already escaped user input into a LIKE contains pattern."""
    return f"%{escape_like(value)}%"


class StaleVersionError(Exception):
    """A write was attempted against a no-longer-current version."""

    def __init__(self, current_version: int | None = None) -> None:
        if current_version is None:
            message = (
                "Version conflict: the resource was modified concurrently, "
                "reload and retry"
            )
        else:
            message = (
                f"Version conflict: current version is {current_version}, "
                "reload and retry"
            )
        super().__init__(message)
        self.current_version = current_version


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
    """Apply a partial update; the router enforces the If-Match precondition.

    The version bump plus SQLAlchemy's ``version_id_col`` check still guard
    against races between loading and committing.
    """
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(binder, key, value)
    binder.version = binder.version + 1
    try:
        session.commit()
    except StaleDataError as exc:
        session.rollback()
        raise StaleVersionError(binder.version) from exc
    session.refresh(binder)
    return binder


def delete_binder(session: Session, binder: Binder) -> None:
    """Delete a binder; the database cascades to cards and certificates."""
    session.delete(binder)
    try:
        session.commit()
    except StaleDataError as exc:
        session.rollback()
        raise StaleVersionError from exc


# --- Cards ---


def get_card_with_certificate(session: Session, card_id: int) -> Card | None:
    """Return the card with eagerly loaded certificate, or None."""
    stmt = (
        select(Card).where(Card.id == card_id).options(selectinload(Card.certificate))
    )
    return session.scalars(stmt).first()


def list_cards(
    session: Session,
    *,
    binder_id: int | None,
    name: str | None,
    set_name: str | None,
    rarity: str | None,
    variant: str | None,
    acquired_from: date | None,
    acquired_to: date | None,
    order_by: CardOrderBy | None,
    order: SortOrder,
    limit: int,
    offset: int,
) -> Sequence[Card]:
    """List cards with optional filters, ordering and pagination."""
    stmt = select(Card).options(selectinload(Card.certificate))
    if binder_id is not None:
        stmt = stmt.where(Card.binder_id == binder_id)
    if name is not None:
        stmt = stmt.where(Card.name.ilike(contains(name), escape="\\"))
    if set_name is not None:
        stmt = stmt.where(Card.set_name.ilike(contains(set_name), escape="\\"))
    if rarity is not None:
        stmt = stmt.where(Card.rarity.ilike(escape_like(rarity), escape="\\"))
    if variant is not None:
        stmt = stmt.where(Card.variant.ilike(escape_like(variant), escape="\\"))
    if acquired_from is not None:
        stmt = stmt.where(Card.acquired_at >= acquired_from)
    if acquired_to is not None:
        stmt = stmt.where(Card.acquired_at <= acquired_to)
    if order_by is None:
        stmt = stmt.order_by(Card.id.desc() if order == "desc" else Card.id.asc())
    else:
        column = CARD_ORDER_COLUMNS[order_by]
        stmt = stmt.order_by(
            column.desc() if order == "desc" else column.asc(), Card.id.asc()
        )
    return session.scalars(stmt.limit(limit).offset(offset)).all()


def create_card(session: Session, data: CardCreate) -> Card:
    """Persist a new card in the given binder."""
    values = data.model_dump(exclude_unset=True)
    card = Card(**{key: value for key, value in values.items() if value is not None})
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


def update_card(session: Session, card: Card, data: CardUpdate) -> Card:
    """Apply a partial update; the router enforces the If-Match precondition."""
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(card, key, value)
    card.version = card.version + 1
    try:
        session.commit()
    except StaleDataError as exc:
        session.rollback()
        raise StaleVersionError(card.version) from exc
    session.refresh(card)
    return card


def delete_card(session: Session, card: Card) -> None:
    """Delete a card; the database cascades its certificate."""
    session.delete(card)
    try:
        session.commit()
    except StaleDataError as exc:
        session.rollback()
        raise StaleVersionError from exc


def search_cards(
    session: Session, query: str, limit: int
) -> list[tuple[Card, str, float]]:
    """Fuzzy-search cards by name, set name and collector number.

    Returns ``(card, binder_name, score)`` tuples ordered by descending score.
    """
    stmt = (
        select(Card, Binder.name)
        .join(Binder, Card.binder_id == Binder.id)
        .options(selectinload(Card.certificate))
    )
    rows = session.execute(stmt).all()
    candidates = [
        (f"{card.name} {card.set_name} {card.collector_number}", card, binder_name)
        for card, binder_name in rows
    ]
    if not candidates:
        return []
    matches = process.extract(
        query,
        [candidate[0] for candidate in candidates],
        scorer=fuzz.WRatio,
        limit=limit,
    )
    return [
        (candidates[index][1], candidates[index][2], float(score))
        for _, score, index in matches
    ]


# --- Certificates ---


def get_certificate(session: Session, certificate_id: int) -> GradingCertificate | None:
    """Return the certificate with the given id, or None."""
    return session.get(GradingCertificate, certificate_id)


def get_certificate_by_cert_number(
    session: Session, cert_number: str
) -> GradingCertificate | None:
    """Return the certificate with the given certificate number, or None."""
    stmt = select(GradingCertificate).where(
        GradingCertificate.cert_number == cert_number
    )
    return session.scalars(stmt).first()


def list_certificates(
    session: Session,
    *,
    card_id: int | None,
    grading_company: str | None,
    grade_min: float | None,
    grade_max: float | None,
    order_by: CertificateOrderBy | None,
    order: SortOrder,
    limit: int,
    offset: int,
) -> Sequence[GradingCertificate]:
    """List certificates with optional filters, ordering and pagination."""
    stmt = select(GradingCertificate)
    if card_id is not None:
        stmt = stmt.where(GradingCertificate.card_id == card_id)
    if grading_company is not None:
        stmt = stmt.where(
            GradingCertificate.grading_company.ilike(
                escape_like(grading_company), escape="\\"
            )
        )
    if grade_min is not None:
        stmt = stmt.where(GradingCertificate.grade >= grade_min)
    if grade_max is not None:
        stmt = stmt.where(GradingCertificate.grade <= grade_max)
    if order_by is None:
        stmt = stmt.order_by(
            GradingCertificate.id.desc()
            if order == "desc"
            else GradingCertificate.id.asc()
        )
    elif order_by == "grade":
        stmt = stmt.order_by(
            GradingCertificate.grade.desc()
            if order == "desc"
            else GradingCertificate.grade.asc(),
            GradingCertificate.id.asc(),
        )
    else:
        stmt = stmt.order_by(
            GradingCertificate.graded_at.desc()
            if order == "desc"
            else GradingCertificate.graded_at.asc(),
            GradingCertificate.id.asc(),
        )
    return session.scalars(stmt.limit(limit).offset(offset)).all()


def create_certificate(
    session: Session, card: Card, data: CertificateCreate
) -> GradingCertificate:
    """Persist a new grading certificate; bumps the card's version.

    Attaching a certificate changes the card's GET representation, so a
    concurrent card update conflicts instead of being lost.
    """
    certificate = GradingCertificate(**data.model_dump())
    session.add(certificate)
    card.version = card.version + 1
    try:
        session.commit()
    except StaleDataError as exc:
        session.rollback()
        raise StaleVersionError(card.version) from exc
    session.refresh(certificate)
    return certificate


def delete_certificate(session: Session, certificate: GradingCertificate) -> None:
    """Delete a grading certificate; bumps the card's version.

    The card becomes ungraded again, which is also a visible change.
    """
    card = certificate.card
    card.version = card.version + 1
    session.delete(certificate)
    try:
        session.commit()
    except StaleDataError as exc:
        session.rollback()
        raise StaleVersionError(card.version) from exc
