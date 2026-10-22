"""Quicksearch endpoint for fuzzy card search."""

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app import conditional, crud
from app.db import get_db
from app.schemas import CardRead, SearchResultItem

router = APIRouter(tags=["search"], route_class=conditional.ConditionalGetRoute)


@router.get(
    "/search",
    response_model=list[SearchResultItem],
    summary="Quicksearch cards",
    responses={
        200: {"headers": conditional.RESPONSE_HEADERS_ETAG},
        304: {"description": "Not modified (If-None-Match matched)."},
    },
)
def search(
    *,
    session: Session = Depends(get_db),
    response: Response,
    q: str = Query(
        min_length=1,
        max_length=100,
        description=(
            "Fuzzy search text; matches card name, set name and collector number."
        ),
    ),
    limit: int = Query(default=20, ge=1, le=50, description="Maximum number of hits."),
) -> list[SearchResultItem]:
    """Fuzzy-search all cards, ranked by match quality."""
    results = crud.search_cards(session, q, limit)
    items = [
        SearchResultItem(
            card=CardRead.model_validate(card),
            binder_name=binder_name,
            score=score,
        )
        for card, binder_name, score in results
    ]
    response.headers["ETag"] = conditional.etag_for_search(
        (item.card.id, item.card.version, item.binder_name) for item in items
    )
    return items
