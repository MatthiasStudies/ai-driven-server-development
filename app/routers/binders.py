"""Endpoints for managing binders."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.db import get_db
from app.models import Binder
from app.schemas import BinderCreate, BinderDetail, BinderRead, BinderUpdate

router = APIRouter(prefix="/binders", tags=["binders"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=BinderRead,
    summary="Create a binder",
)
def create_binder(data: BinderCreate, session: Session = Depends(get_db)) -> Binder:
    """Create a new, empty binder."""
    return crud.create_binder(session, data)


@router.get("", response_model=list[BinderRead], summary="List binders")
def list_binders(
    *,
    session: Session = Depends(get_db),
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
    return crud.list_binders(
        session, name=name, order_by=order_by, order=order, limit=limit, offset=offset
    )


@router.get("/{binder_id}", response_model=BinderDetail, summary="Get a binder")
def get_binder(binder_id: int, session: Session = Depends(get_db)) -> Binder:
    """Return a single binder including its cards."""
    binder = crud.get_binder_with_cards(session, binder_id)
    if binder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Binder not found"
        )
    return binder


@router.put("/{binder_id}", response_model=BinderRead, summary="Update a binder")
def update_binder(
    binder_id: int, data: BinderUpdate, session: Session = Depends(get_db)
) -> Binder:
    """Partially update a binder; omitted fields keep their values."""
    binder = crud.get_binder(session, binder_id)
    if binder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Binder not found"
        )
    return crud.update_binder(session, binder, data)


@router.delete(
    "/{binder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a binder",
    responses={
        204: {"description": "Binder deleted (cards and certificates cascade)."}
    },
)
def delete_binder(binder_id: int, session: Session = Depends(get_db)) -> None:
    """Delete a binder; its cards and certificates are removed as well."""
    binder = crud.get_binder(session, binder_id)
    if binder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Binder not found"
        )
    crud.delete_binder(session, binder)
