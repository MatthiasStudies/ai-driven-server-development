"""Crud-level tests for the optimistic locking mechanism."""

import pytest
from sqlalchemy.engine import Engine

from app import crud
from app.db import get_session_factory
from app.schemas import BinderUpdate


def test_concurrent_binder_updates_raise_stale_version(
    database: Engine,
) -> None:
    """Two sessions updating the same row: the losing commit must fail."""
    factory = get_session_factory()
    winner = factory()
    loser = factory()
    try:
        winner_binder = crud.get_binder(winner, 3)
        loser_binder = crud.get_binder(loser, 3)
        assert winner_binder is not None
        assert loser_binder is not None

        crud.update_binder(
            winner,
            winner_binder,
            BinderUpdate(version=winner_binder.version, name="Winner"),
        )
        with pytest.raises(crud.StaleVersionError):
            crud.update_binder(
                loser,
                loser_binder,
                BinderUpdate(version=loser_binder.version, name="Loser"),
            )
    finally:
        winner.close()
        loser.close()


def test_stale_version_error_reports_current_version(database: Engine) -> None:
    """The application-level check exposes the current version."""
    factory = get_session_factory()
    session = factory()
    try:
        binder = crud.get_binder(session, 3)
        assert binder is not None
        with pytest.raises(crud.StaleVersionError) as exc_info:
            crud.update_binder(
                session,
                binder,
                BinderUpdate(version=binder.version + 5, name="Too new"),
            )
        assert exc_info.value.current_version == binder.version
    finally:
        session.close()
