"""Shared pytest fixtures for the integration test suite.

The suite runs against a dedicated ``tcg_tracker_test`` database that is
recreated from ``postgres-data/init.sql`` once per test session; every test
starts from the seed data.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from app import db as app_db
from app.config import get_settings
from app.main import app

INIT_SQL_PATH = Path(__file__).resolve().parent.parent / "postgres-data" / "init.sql"
SEED_MARKER = "-- 2. SEED DATA"
TRUNCATE_SQL = "TRUNCATE grading_certificates, cards, binders RESTART IDENTITY CASCADE"


def _executable_statements(sql: str) -> list[str]:
    """Split SQL text into statements, skipping comment-only chunks."""
    statements = []
    for chunk in sql.split(";"):
        lines = [
            line
            for line in chunk.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ]
        if lines:
            statements.append(chunk.strip())
    return statements


def _split_init_sql() -> tuple[list[str], list[str]]:
    """Split init.sql into schema and seed statements."""
    raw = INIT_SQL_PATH.read_text(encoding="utf-8")
    ddl_part, _, seed_part = raw.partition(SEED_MARKER)
    return _executable_statements(ddl_part), _executable_statements(seed_part)


@pytest.fixture(scope="session")
def _recreated_test_database() -> str:
    """Create a fresh test database from init.sql and point the app at it."""
    settings = get_settings()
    test_url = make_url(settings.test_sync_database_url)
    admin_url = test_url.set(database="postgres").render_as_string(hide_password=False)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(
                text(f'DROP DATABASE IF EXISTS "{test_url.database}" WITH (FORCE)')
            )
            conn.execute(text(f'CREATE DATABASE "{test_url.database}"'))
    finally:
        admin_engine.dispose()

    app_db.set_database_url(settings.test_sync_database_url)
    ddl, seed = _split_init_sql()
    with app_db.get_engine().begin() as conn:
        for statement in ddl + seed:
            conn.execute(text(statement))
    return settings.test_sync_database_url


@pytest.fixture
def database(_recreated_test_database: str) -> Iterator[Engine]:
    """Reset all tables to the seed state before each test."""
    _, seed = _split_init_sql()
    with app_db.get_engine().begin() as conn:
        conn.execute(text(TRUNCATE_SQL))
        for statement in seed:
            conn.execute(text(statement))
    yield app_db.get_engine()


@pytest.fixture
def client(database: Engine) -> Iterator[TestClient]:
    """HTTP client backed by the per-test seeded database."""
    with TestClient(app) as test_client:
        yield test_client
