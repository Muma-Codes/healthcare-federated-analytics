"""
Each row records one attempt at the security awareness training quiz.
The user's last_training_date on the User model is updated to now()
whenever they pass (score >= 4/5).

Used by:
  - POST /training/complete -> inserts a row here
  - GET  /training/status -> checks User.last_training_date
  - GET  /admin/dashboard-stats -> counts compliant vs non-compliant users
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from database.base import Base


class TrainingCompletion(Base):
    __tablename__ = "training_completions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score = Column(Integer, nullable=False)   # 0-5
    passed = Column(Boolean, nullable=False)
    completed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="training_completions")