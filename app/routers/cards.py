"""Endpoints for managing cards."""

from collections.abc import Sequence
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app import conditional, crud
from app.crud import StaleVersionError
from app.db import get_db
from app.models import Card
from app.schemas import CardCreate, CardRead, CardUpdate

router = APIRouter(
    prefix="/cards",
    tags=["cards"],
    route_class=conditional.ConditionalGetRoute,
)

IF_MATCH_DESCRIPTION = "ETag from the last GET of this card."


def _card_etag(card: Card) -> str:
    return conditional.etag_for("card", card.id, card.version)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CardRead,
    summary="Create a card",
)
def create_card(data: CardCreate, session: Session = Depends(get_db)) -> Card:
    """Create a new card in an existing binder."""
    binder = crud.get_binder(session, data.binder_id)
    if binder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Binder not found"
        )
    return crud.create_card(session, data)


@router.get(
    "",
    response_model=list[CardRead],
    summary="List cards",
    responses={
        200: {"headers": conditional.RESPONSE_HEADERS_ETAG},
        304: {"description": "Not modified (If-None-Match matched)."},
    },
)
def list_cards(
    *,
    session: Session = Depends(get_db),
    response: Response,
    binder_id: int | None = Query(
        default=None, description="Only cards in this binder."
    ),
    name: str | None = Query(
        default=None,
        max_length=100,
        description="Case-insensitive substring filter on the card name.",
    ),
    set_name: str | None = Query(
        default=None,
        max_length=100,
        description="Case-insensitive substring filter on the set name.",
    ),
    rarity: str | None = Query(
        default=None,
        max_length=50,
        description="Case-insensitive exact filter on the rarity.",
    ),
    variant: str | None = Query(
        default=None,
        max_length=50,
        description="Case-insensitive exact filter on the variant.",
    ),
    acquired_from: date | None = Query(
        default=None, description="Only cards acquired on or after this date."
    ),
    acquired_to: date | None = Query(
        default=None, description="Only cards acquired on or before this date."
    ),
    order_by: crud.CardOrderBy | None = Query(
        default=None,
        description="Field to order by. Defaults to insertion order.",
    ),
    order: crud.SortOrder = Query(default="asc", description="Sort direction."),
    limit: int = Query(default=50, ge=1, le=100, description="Page size."),
    offset: int = Query(default=0, ge=0, description="Number of items to skip."),
) -> Sequence[Card]:
    """List cards with optional filtering, ordering and pagination."""
    cards = crud.list_cards(
        session,
        binder_id=binder_id,
        name=name,
        set_name=set_name,
        rarity=rarity,
        variant=variant,
        acquired_from=acquired_from,
        acquired_to=acquired_to,
        order_by=order_by,
        order=order,
        limit=limit,
        offset=offset,
    )
    response.headers["ETag"] = conditional.etag_for_collection(
        "cards", [(card.id, card.version) for card in cards]
    )
    return cards


@router.get(
    "/{card_id}",
    response_model=CardRead,
    summary="Get a card",
    responses={
        200: {"headers": conditional.RESPONSE_HEADERS_ETAG},
        304: {"description": "Not modified (If-None-Match matched)."},
    },
)
def get_card(
    card_id: int, response: Response, session: Session = Depends(get_db)
) -> Card:
    """Return a single card including its certificate if graded."""
    card = crud.get_card_with_certificate(session, card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card not found"
        )
    response.headers["ETag"] = _card_etag(card)
    return card


@router.put(
    "/{card_id}",
    response_model=CardRead,
    summary="Update a card",
    responses={
        200: {"headers": conditional.RESPONSE_HEADERS_ETAG},
        412: {"description": "Precondition failed (stale If-Match)"},
        428: {"description": "If-Match header missing"},
    },
)
def update_card(
    card_id: int,
    data: CardUpdate,
    response: Response,
    session: Session = Depends(get_db),
    if_match: str | None = Header(
        default=None, alias="If-Match", description=IF_MATCH_DESCRIPTION
    ),
) -> Card:
    """Partially update a card guarded by the If-Match precondition."""
    card = crud.get_card_with_certificate(session, card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card not found"
        )
    conditional.enforce_if_match(if_match, _card_etag(card))
    if data.binder_id is not None and crud.get_binder(session, data.binder_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Binder not found"
        )
    try:
        updated = crud.update_card(session, card, data)
    except StaleVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED, detail=str(exc)
        ) from exc
    response.headers["ETag"] = _card_etag(updated)
    return updated


@router.delete(
    "/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a card",
    responses={
        204: {"description": "Card deleted (its certificate cascades)."},
        412: {"description": "Precondition failed (stale If-Match)"},
        428: {"description": "If-Match header missing"},
    },
)
def delete_card(
    card_id: int,
    session: Session = Depends(get_db),
    if_match: str | None = Header(
        default=None, alias="If-Match", description=IF_MATCH_DESCRIPTION
    ),
) -> None:
    """Delete a card guarded by the If-Match precondition."""
    card = crud.get_card_with_certificate(session, card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card not found"
        )
    conditional.enforce_if_match(if_match, _card_etag(card))
    try:
        crud.delete_card(session, card)
    except StaleVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED, detail=str(exc)
        ) from exc
