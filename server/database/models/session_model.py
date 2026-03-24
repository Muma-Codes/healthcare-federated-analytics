"""
Tracks active JWT sessions in the database.
When a user logs out or their token expires, the session is
marked is_active=False. The auth dependency checks this table
on every protected request, which allows server-side logout
(something pure JWT cannot do alone).

Named UserSession (not Session) to avoid clash with SQLAlchemy's
own Session class.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database.base import Base


class UserSession(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(200), nullable=False, unique=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    ip_address = Column(String(45), nullable=True)

    user = relationship("User", back_populates="sessions")