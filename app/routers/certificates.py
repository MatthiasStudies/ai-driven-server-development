"""Endpoints for managing grading certificates."""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import conditional, crud
from app.crud import StaleVersionError
from app.db import get_db
from app.models import GradingCertificate
from app.schemas import CertificateCreate, CertificateRead

router = APIRouter(
    prefix="/certificates",
    tags=["certificates"],
    route_class=conditional.ConditionalGetRoute,
)


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
    card = crud.get_card_with_certificate(session, data.card_id)
    if card is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Card not found"
        )
    if card.certificate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Card is already graded"
        )
    if crud.get_certificate_by_cert_number(session, data.cert_number) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Certificate number already exists",
        )
    try:
        return crud.create_certificate(session, card, data)
    except StaleVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Certificate conflict"
        ) from exc


@router.get(
    "",
    response_model=list[CertificateRead],
    summary="List grading certificates",
    responses={
        200: {"headers": conditional.RESPONSE_HEADERS_ETAG},
        304: {"description": "Not modified (If-None-Match matched)."},
    },
)
def list_certificates(
    *,
    session: Session = Depends(get_db),
    response: Response,
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
    certificates = crud.list_certificates(
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
    response.headers["ETag"] = conditional.etag_for_immutable_collection(
        "certificates", (certificate.id for certificate in certificates)
    )
    return certificates


@router.get(
    "/{certificate_id}",
    response_model=CertificateRead,
    summary="Get a grading certificate",
    responses={
        200: {"headers": conditional.RESPONSE_HEADERS_ETAG},
        304: {"description": "Not modified (If-None-Match matched)."},
    },
)
def get_certificate(
    certificate_id: int, response: Response, session: Session = Depends(get_db)
) -> GradingCertificate:
    """Return a single grading certificate."""
    certificate = crud.get_certificate(session, certificate_id)
    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found"
        )
    response.headers["ETag"] = conditional.etag_for_immutable(
        "certificate", certificate.id
    )
    return certificate


@router.delete(
    "/{certificate_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a grading certificate",
    responses={
        204: {"description": "Certificate deleted; the card is ungraded."},
        409: {"description": "Version conflict (card changed concurrently)"},
    },
)
def delete_certificate(certificate_id: int, session: Session = Depends(get_db)) -> None:
    """Remove a grading certificate from its card."""
    certificate = crud.get_certificate(session, certificate_id)
    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found"
        )
    try:
        crud.delete_certificate(session, certificate)
    except StaleVersionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
