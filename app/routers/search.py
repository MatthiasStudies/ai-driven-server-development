"""Quicksearch endpoint for fuzzy card search."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud
from app.db import get_db
from app.schemas import CardRead, SearchResultItem

router = APIRouter(tags=["search"])


@router.get(
    "/search",
    response_model=list[SearchResultItem],
    summary="Quicksearch cards",
)
def search(
    *,
    session: Session = Depends(get_db),
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
    return [
        SearchResultItem(
            card=CardRead.model_validate(card),
            binder_name=binder_name,
            score=score,
        )
        for card, binder_name, score in results
    ]
