"""Crud-level tests for the optimistic locking mechanism."""

from sqlalchemy.engine import Engine

import pytest

from app import crud
from app.db import get_session_factory
from app.schemas import BinderUpdate


def test_concurrent_binder_updates_raise_stale_version(database: Engine) -> None:
    """Two sessions updating the same row: the losing commit must fail.

    This exercises the version_id_col backstop that protects the window
    between the If-Match check and the commit.
    """
    factory = get_session_factory()
    winner = factory()
    loser = factory()
    try:
        winner_binder = crud.get_binder(winner, 3)
        loser_binder = crud.get_binder(loser, 3)
        assert winner_binder is not None
        assert loser_binder is not None

        crud.update_binder(winner, winner_binder, BinderUpdate(name="Winner"))
        with pytest.raises(crud.StaleVersionError):
            crud.update_binder(loser, loser_binder, BinderUpdate(name="Loser"))
    finally:
        winner.close()
        loser.close()
