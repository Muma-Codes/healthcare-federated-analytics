"""
Immutable record of every significant action in the system.
Written to on every login attempt, prediction, role change, etc.
Admins view this via GET /admin/audit-logs.

Common action strings:
  REGISTER            - new self-registration submitted
  ACCOUNT_APPROVED    - admin approved + assigned role
  LOGIN_SUCCESS       - successful authentication
  LOGIN_FAIL          - wrong password
  LOGIN_BLOCKED_LOCKED - blocked because account is locked
  LOGOUT              - explicit logout
  PASSWORD_CHANGED    - user changed their own password
  MFA_ENABLED         - user activated TOTP MFA
  PREDICT_DIABETES    - diabetes prediction run
  PREDICT_HEART       - heart prediction run
  USER_LOCKED         - account locked after too many failures
  USER_UNLOCKED       - admin unlocked the account
  ROLE_UPDATED        - admin changed a user's role
  USER_DEACTIVATED    - admin deactivated an account
  TRAINING_COMPLETED  - security training quiz submitted
  FL_TRAINING_STARTED - admin triggered federated training
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(100), nullable=True)
    detail = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    success = Column(Boolean, default=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    user = relationship("User", back_populates="audit_logs")