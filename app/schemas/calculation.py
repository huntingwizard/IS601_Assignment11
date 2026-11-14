"""
Pydantic schemas for calculations.

CalculationCreate validates what a client sends in; CalculationRead describes
what is sent back. Validation happens here, before anything touches the
database.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class CalculationType(str, Enum):
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"


_ALIASES = {"sub": "subtract"}


def normalise_type_name(value):
    """Lower-case and trim a type name; map short aliases. Non-strings pass through."""
    if isinstance(value, str):
        cleaned = value.strip().lower()
        return _ALIASES.get(cleaned, cleaned)
    return value


class CalculationCreate(BaseModel):
    a: float = Field(..., allow_inf_nan=False, description="First operand")
    b: float = Field(..., allow_inf_nan=False, description="Second operand")
    type: CalculationType = Field(..., description="add, subtract, multiply or divide")
    user_id: Optional[UUID] = Field(None, description="Owner of the calculation")

    @field_validator("type", mode="before")
    @classmethod
    def normalise_type(cls, value):
        return normalise_type_name(value)

    @model_validator(mode="after")
    def reject_zero_divisor(self):
        if self.type == CalculationType.DIVIDE and self.b == 0:
            raise ValueError("Cannot divide by zero")
        return self


class CalculationRead(BaseModel):
    id: UUID
    a: float
    b: float
    type: CalculationType
    result: Optional[float] = None
    user_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)