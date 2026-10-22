"""Application configuration loaded from environment variables and .env files.

Variable names mirror the official Postgres image, so a single ``.env`` file
can configure both the docker-compose service and the application.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    """Database and application settings.

    Values are read from environment variables or a ``.env`` file in the
    project root. Defaults match the local development setup from
    ``project.md``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_user: str = "tcg_user"
    postgres_password: str = "tcg_password"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "tcg_tracker"

    database_url: str | None = None
    test_database_url: str | None = None

    def compose_database_url(self, database: str) -> str:
        """Build a psycopg sync URL for the given database name."""
        url = URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=database,
        )
        return url.render_as_string(hide_password=False)

    @property
    def sync_database_url(self) -> str:
        """Database URL used by the application engine."""
        if self.database_url is not None:
            return self.database_url
        return self.compose_database_url(self.postgres_db)

    @property
    def test_sync_database_url(self) -> str:
        """Database URL used by the test suite; defaults to ``<db>_test``."""
        if self.test_database_url is not None:
            return self.test_database_url
        base = make_url(self.sync_database_url)
        return base.set(database=f"{base.database}_test").render_as_string(
            hide_password=False
        )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()
