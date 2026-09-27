from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ConversationSession, Marker


class SessionRepository:
    def __init__(self, db: Session, owner_id: str):
        self.db = db
        self.owner_id = owner_id

    def get(self, session_id: str) -> ConversationSession | None:
        return self.db.scalar(
            select(ConversationSession).where(
                ConversationSession.id == session_id,
                ConversationSession.owner_id == self.owner_id,
            )
        )

    def list(self) -> list[ConversationSession]:
        return list(
            self.db.scalars(
                select(ConversationSession)
                .where(ConversationSession.owner_id == self.owner_id)
                .order_by(ConversationSession.created_at.desc())
            )
        )

    def markers(self, session_id: str) -> list[Marker]:
        return list(
            self.db.scalars(select(Marker).where(Marker.session_id == session_id).order_by(Marker.timestamp_ms))
        )

