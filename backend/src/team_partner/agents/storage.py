from collections.abc import AsyncIterator
from datetime import datetime

from hyperforge.harness_sdk import HarnessConversation, HarnessEvent, HarnessMemory, HarnessStorageProtocol
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from team_partner.db import ConversationRow, EventRow, MemoryRow, transaction


class SQLiteHarnessStorage(HarnessStorageProtocol):
    """Persist Hyperforge conversations and ordered events."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self.factory = factory

    async def create_conversation(self, conversation: HarnessConversation) -> None:
        with transaction(self.factory) as session:
            session.add(
                ConversationRow(
                    id=conversation.id,
                    title=conversation.title,
                    category=conversation.category,
                    tags=conversation.tags,
                    details=conversation.metadata,
                    created_datetime=conversation.created_datetime.isoformat(),
                    updated_datetime=conversation.updated_datetime.isoformat(),
                )
            )

    async def get_conversation(self, conversation_id: str) -> HarnessConversation | None:
        with self.factory() as session:
            row = session.get(ConversationRow, conversation_id)
            if row is None:
                return None
            return self._conversation(row)

    async def update_conversation(self, conversation: HarnessConversation) -> None:
        with transaction(self.factory) as session:
            row = session.get(ConversationRow, conversation.id)
            if row is None:
                raise ValueError("Conversation not found")
            row.title = conversation.title
            row.category = conversation.category
            row.tags = conversation.tags
            row.details = conversation.metadata
            row.updated_datetime = conversation.updated_datetime.isoformat()

    async def append_event(self, event: HarnessEvent) -> None:
        with transaction(self.factory) as session:
            row = session.get(ConversationRow, event.conversation_id)
            if row is None:
                raise ValueError("Conversation not found")
            session.add(
                EventRow(
                    id=event.id,
                    conversation_id=event.conversation_id,
                    data=event.model_dump(mode="json"),
                )
            )
            row.updated_datetime = max(row.updated_datetime, event.created_datetime.isoformat())

    async def iter_events(self, conversation_id: str) -> AsyncIterator[HarnessEvent]:
        with self.factory() as session:
            rows = session.scalars(
                select(EventRow)
                .join(ConversationRow)
                .where(ConversationRow.id == conversation_id)
                .order_by(EventRow.sequence)
            ).all()
        for row in rows:
            yield HarnessEvent.model_validate(row.data)

    async def remember(self, memory: HarnessMemory) -> None:
        with transaction(self.factory) as session:
            session.add(
                MemoryRow(
                    id=memory.id,
                    scope=memory.scope,
                    text=memory.text,
                    data=memory.model_dump(mode="json"),
                    created_datetime=memory.created_datetime.isoformat(),
                )
            )

    async def recall(self, *, scope: str, query: str, limit: int = 20) -> list[HarnessMemory]:
        with self.factory() as session:
            stmt = select(MemoryRow).where(MemoryRow.scope == scope)
            if query.strip():
                stmt = stmt.where(MemoryRow.text.icontains(query.strip(), autoescape=True))
            rows = session.scalars(stmt.order_by(MemoryRow.created_datetime.desc()).limit(limit)).all()
        return [HarnessMemory.model_validate(row.data) for row in rows]

    async def forget(self, memory_id: str) -> None:
        with transaction(self.factory) as session:
            session.execute(delete(MemoryRow).where(MemoryRow.id == memory_id))

    def list_conversations(self, *, limit: int = 50) -> list[HarnessConversation]:
        with self.factory() as session:
            rows = session.scalars(
                select(ConversationRow).order_by(ConversationRow.updated_datetime.desc()).limit(limit)
            ).all()
            return [self._conversation(row) for row in rows]

    def delete_conversation(self, conversation_id: str) -> bool:
        with transaction(self.factory) as session:
            row = session.get(ConversationRow, conversation_id)
            if row is None:
                return False
            session.delete(row)
            return True

    @staticmethod
    def _conversation(row: ConversationRow) -> HarnessConversation:
        return HarnessConversation(
            id=row.id,
            title=row.title,
            category=row.category,
            tags=row.tags,
            metadata=row.details,
            created_datetime=datetime.fromisoformat(row.created_datetime),
            updated_datetime=datetime.fromisoformat(row.updated_datetime),
        )
