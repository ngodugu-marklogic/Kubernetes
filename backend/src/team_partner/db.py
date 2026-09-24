from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    pass


class ConversationRow(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    tags: Mapped[list[str]] = mapped_column(JSON)
    details: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_datetime: Mapped[str] = mapped_column(String)
    updated_datetime: Mapped[str] = mapped_column(String)
    events: Mapped[list["EventRow"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class EventRow(Base):
    __tablename__ = "events"

    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String, unique=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    conversation: Mapped[ConversationRow] = relationship(back_populates="events")


class MemoryRow(Base):
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scope: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(String)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_datetime: Mapped[str] = mapped_column(String)


class TeamMemberRow(Base):
    __tablename__ = "team_members"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    jira_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
    github_login: Mapped[str | None] = mapped_column(String, nullable=True)
    ownership: Mapped[str | None] = mapped_column(String, nullable=True)


class JiraTeamRow(Base):
    __tablename__ = "jira_teams"

    board_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    project_key: Mapped[str | None] = mapped_column(String, nullable=True)
    site_url: Mapped[str | None] = mapped_column(String, nullable=True)


class GitHubRepoRow(Base):
    __tablename__ = "github_repos"

    full_name: Mapped[str] = mapped_column(String, primary_key=True)


def create_database(url: str) -> tuple[Engine, sessionmaker[Session]]:
    if not url.startswith("sqlite:"):
        raise ValueError("Only SQLite database URLs are supported")
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


@contextmanager
def transaction(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory.begin() as session:
        yield session
