from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.config import PROJECT_ROOT, get_settings
from app.database.session import make_engine


def alembic_config(database_url: str | None = None) -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "app/database/migrations"))
    cfg.attributes["database_url"] = database_url or get_settings().database_url.get_secret_value()
    cfg.attributes["configure_logger"] = False
    return cfg


def upgrade_head(database_url: str | None = None) -> None:
    command.upgrade(alembic_config(database_url), "head")


def current_revision(database_url: str | None = None) -> str | None:
    url = database_url or get_settings().database_url.get_secret_value()
    engine = make_engine(url)
    try:
        with engine.connect() as conn:
            if not inspect(conn).has_table("alembic_version"):
                return None
            from sqlalchemy import text

            return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    finally:
        engine.dispose()
