"""Endpoints for managing grading certificates."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud
from app.db import get_db
from app.models import GradingCertificate
from app.schemas import CertificateCreate, CertificateRead

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CertificateRead,
    summary="Add a grading certificate to an existing card",
    responses={
        404: {"description": "Card not found"},
        409: {"description": "Card already graded or certificate number taken"},
    },
)
def create_certificate(
    data: CertificateCreate, session: Session = Depends(get_db)
) -> GradingCertificate:
    """Attach a grading certificate to a card that is not graded yet."""
    if crud.get_card_with_certificate(session, data.card_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card not found"
        )
    if crud.get_certificate_for_card(session, data.card_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Card is already graded"
        )
    if crud.get_certificate_by_cert_number(session, data.cert_number) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Certificate number already exists",
        )
    try:
        return crud.create_certificate(session, data)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Certificate conflict"
        ) from exc


@router.get(
    "", response_model=list[CertificateRead], summary="List grading certificates"
)
def list_certificates(
    *,
    session: Session = Depends(get_db),
    card_id: int | None = Query(
        default=None, description="Only the certificate of this card."
    ),
    grading_company: str | None = Query(
        default=None,
        max_length=20,
        description="Case-insensitive exact filter on the grading company.",
    ),
    grade_min: float | None = Query(
        default=None, ge=1.0, le=10.0, description="Minimum grade (inclusive)."
    ),
    grade_max: float | None = Query(
        default=None, ge=1.0, le=10.0, description="Maximum grade (inclusive)."
    ),
    order_by: crud.CertificateOrderBy | None = Query(
        default=None,
        description="Field to order by. Defaults to insertion order.",
    ),
    order: crud.SortOrder = Query(default="asc", description="Sort direction."),
    limit: int = Query(default=50, ge=1, le=100, description="Page size."),
    offset: int = Query(default=0, ge=0, description="Number of items to skip."),
) -> Sequence[GradingCertificate]:
    """List grading certificates with optional filtering and ordering."""
    return crud.list_certificates(
        session,
        card_id=card_id,
        grading_company=grading_company,
        grade_min=grade_min,
        grade_max=grade_max,
        order_by=order_by,
        order=order,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{certificate_id}",
    response_model=CertificateRead,
    summary="Get a grading certificate",
)
def get_certificate(
    certificate_id: int, session: Session = Depends(get_db)
) -> GradingCertificate:
    """Return a single grading certificate."""
    certificate = crud.get_certificate(session, certificate_id)
    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found"
        )
    return certificate


@router.delete(
    "/{certificate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a grading certificate",
    responses={204: {"description": "Certificate deleted; the card is ungraded."}},
)
def delete_certificate(certificate_id: int, session: Session = Depends(get_db)) -> None:
    """Remove a grading certificate from its card."""
    certificate = crud.get_certificate(session, certificate_id)
    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found"
        )
    crud.delete_certificate(session, certificate)
