from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .core.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_development_database() -> None:
    if settings.auto_create_schema and not settings.production:
        from . import models  # noqa: F401

        Base.metadata.create_all(bind=engine)
        # Existing development databases were created without Alembic history.
        # Add only the new preference fields; production uses migration 0007.
        with engine.begin() as connection:
            for table, additions in {
                "user_preferences": [("date_format", "auto"), ("native_language", "zh"), ("target_language", "en")],
                "conversation_sessions": [("target_language", "en")],
                "practices_v1": [("target_language", "en")],
            }.items():
                columns = {column["name"] for column in inspect(connection).get_columns(table)}
                for name, default in additions:
                    if name not in columns:
                        connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} VARCHAR(8) NOT NULL DEFAULT '{default}'"))

            if "is_favorite" not in {column["name"] for column in inspect(connection).get_columns("conversation_sessions")}:
                connection.execute(text("ALTER TABLE conversation_sessions ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0"))

            if "avatar" not in {column["name"] for column in inspect(connection).get_columns("users")}:
                connection.execute(text("ALTER TABLE users ADD COLUMN avatar TEXT"))

            if "voiceprint_json" not in {column["name"] for column in inspect(connection).get_columns("users")}:
                connection.execute(text("ALTER TABLE users ADD COLUMN voiceprint_json JSON"))
