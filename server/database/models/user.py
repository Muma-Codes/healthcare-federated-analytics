"""
Stores system accounts with all security-related fields:
  - Role-based access control (admin | doctor | nurse | pending)
  - Account lockout after too many failed login attempts
  - Password expiry enforcement
  - MFA (TOTP) support
  - Security training tracking

Roles:
  pending  -> self-registered, cannot log in until admin assigns a real role
  nurse    -> read-only access; can view dashboard and complete training
  doctor   -> can run predictions; cannot manage users
  admin    -> full access; assigns roles, views audit logs, manages users
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from database.base import Base


class User(Base):
    __tablename__ = "users"

    # Identity
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False)
    full_name = Column(String(100), nullable=False)

    # Credentials
    password_hash = Column(String(200), nullable=False)

    # Role / Access
    # "pending" = self-registered but awaiting admin role assignment
    role = Column(String(20), nullable=False, default="pending")

    # Account Status
    is_active = Column(Boolean, default=True)
    is_approved = Column(Boolean, default=False)  # admin has assigned a real role
    is_locked = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Password Policy
    must_change_password = Column(Boolean, default=False)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)

    # MFA / TOTP
    totp_secret = Column(String(64), nullable=True)
    mfa_enabled = Column(Boolean, default=False)

    # Security Training
    last_training_date = Column(DateTime(timezone=True), nullable=True)

    # Timestamps 
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    audit_logs = relationship("AuditLog", back_populates="user")
    prediction_logs = relationship("PredictionLog", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    training_completions = relationship("TrainingCompletion", back_populates="user")