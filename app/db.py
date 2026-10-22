"""Database engine and session management."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return the lazily created application engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().sync_database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the lazily created session factory bound to the current engine."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


def set_database_url(url: str) -> None:
    """Reconfigure the engine to use ``url`` (used by the test suite)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = create_engine(url, pool_pre_ping=True)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Yield a database session, closing it afterwards (FastAPI dependency)."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
