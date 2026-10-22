"""Endpoints for managing binders."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app import conditional, crud
from app.crud import StaleVersionError
from app.db import get_db
from app.models import Binder
from app.schemas import (
    BinderCreate,
    BinderDetail,
    BinderRead,
    BinderUpdate,
)

router = APIRouter(
    prefix="/binders",
    tags=["binders"],
    route_class=conditional.ConditionalGetRoute,
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=BinderRead,
    summary="Create a binder",
)
def create_binder(data: BinderCreate, session: Session = Depends(get_db)) -> Binder:
    """Create a new, empty binder."""
    return crud.create_binder(session, data)


@router.get(
    "",
    response_model=list[BinderRead],
    summary="List binders",
    responses={
        200: {"headers": conditional.RESPONSE_HEADERS_ETAG},
        304: {"description": "Not modified (If-None-Match matched)."},
    },
)
def list_binders(
    *,
    session: Session = Depends(get_db),
    response: Response,
    name: str | None = Query(
        default=None,
        max_length=100,
        description="Case-insensitive substring filter on the binder name.",
    ),
    order_by: crud.BinderOrderBy | None = Query(
        default=None,
        description="Field to order by. Defaults to insertion order.",
    ),
    order: crud.SortOrder = Query(default="asc", description="Sort direction."),
    limit: int = Query(default=50, ge=1, le=100, description="Page size."),
    offset: int = Query(default=0, ge=0, description="Number of items to skip."),
) -> Sequence[Binder]:
    """List binders with optional filtering, ordering and pagination."""
    binders = crud.list_binders(
        session, name=name, order_by=order_by, order=order, limit=limit, offset=offset
    )
    response.headers["ETag"] = conditional.etag_for_collection(
        "binders", [(binder.id, binder.version) for binder in binders]
    )
    return binders


@router.get(
    "/{binder_id}",
    response_model=BinderDetail,
    summary="Get a binder",
    responses={
        200: {"headers": conditional.RESPONSE_HEADERS_ETAG},
        304: {"description": "Not modified (If-None-Match matched)."},
    },
)
def get_binder(
    binder_id: int, response: Response, session: Session = Depends(get_db)
) -> Binder:
    """Return a single binder including its cards."""
    binder = crud.get_binder_with_cards(session, binder_id)
    if binder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Binder not found"
        )
    response.headers["ETag"] = conditional.etag_for_children(
        "binder",
        binder.id,
        binder.version,
        [(card.id, card.version) for card in binder.cards],
    )
    return binder


@router.put(
    "/{binder_id}",
    response_model=BinderRead,
    summary="Update a binder",
    responses={409: {"description": "Version conflict (stale version)"}},
)
def update_binder(
    binder_id: int, data: BinderUpdate, session: Session = Depends(get_db)
) -> Binder:
    """Partially update a binder; the version must match the last read."""
    binder = crud.get_binder(session, binder_id)
    if binder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Binder not found"
        )
    try:
        return crud.update_binder(session, binder, data)
    except StaleVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc


@router.delete(
    "/{binder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a binder",
    responses={
        204: {"description": "Binder deleted (cards and certificates cascade)."},
        409: {"description": "Version conflict (stale version)"},
    },
)
def delete_binder(
    binder_id: int,
    *,
    version: int = Query(
        gt=0,
        description=(
            "Expected version from the last GET; a 409 is returned if the "
            "binder changed since then."
        ),
    ),
    session: Session = Depends(get_db),
) -> None:
    """Delete a binder; the version must match the last read."""
    binder = crud.get_binder(session, binder_id)
    if binder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Binder not found"
        )
    try:
        crud.delete_binder(session, binder, version)
    except StaleVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
