"""
Records every prediction made through the system.

PRIVACY GUARANTEE:
  - No patient name, date of birth, ID number or any personal identifier
    is ever stored in this table.
  - Only anonymised clinical measurement values are stored (the same
    numbers the clinician typed into the prediction form).
  - The 'user_id' links to the clinician who ran the prediction,
    NOT to the patient.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from database.base import Base


class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    disease_type = Column(String(20), nullable=False)   # "diabetes" | "heart"
    input_features = Column(JSON, nullable=False)   # anonymised numeric values only
    prediction = Column(Integer, nullable=False)   # 0 = low risk, 1 = high risk
    confidence = Column(Float, nullable=False)   # 0.0 - 1.0
    model_version = Column(String(20), nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="prediction_logs")