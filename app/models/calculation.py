"""
Calculation model.

One row per calculation. Both operands and the computed result are stored,
so history can be listed without recomputing anything. The database itself
rejects rows that break the rules (unknown operation, division by zero), so
bad data cannot get in even if application code is bypassed.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base

VALID_TYPES = ("add", "subtract", "multiply", "divide")
_TYPE_LIST = ", ".join(f"'{name}'" for name in VALID_TYPES)


class Calculation(Base):
    __tablename__ = "calculations"
    __table_args__ = (
        CheckConstraint(f"type IN ({_TYPE_LIST})", name="ck_calculations_type"),
        CheckConstraint(
            "NOT (type = 'divide' AND b = 0)",
            name="ck_calculations_no_zero_divisor",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    a = Column(Float, nullable=False)
    b = Column(Float, nullable=False)
    type = Column(String(20), nullable=False, index=True)
    result = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="calculations")

    def __repr__(self):
        return f"<Calculation({self.a} {self.type} {self.b} = {self.result})>"