"""
Calculation factory.

Maps a calculation type to the function that performs it and builds
ready-to-save Calculation rows with the result already computed. Supporting
a new operation means adding one enum member and one entry in _OPERATIONS.
"""

from typing import Callable, Dict, List, Optional
from uuid import UUID

from app.models.calculation import Calculation
from app.operations import add, divide, multiply, subtract
from app.schemas.calculation import (
    CalculationCreate,
    CalculationType,
    normalise_type_name,
)

Operation = Callable[[float, float], float]


class CalculationFactory:
    _OPERATIONS: Dict[CalculationType, Operation] = {
        CalculationType.ADD: add,
        CalculationType.SUBTRACT: subtract,
        CalculationType.MULTIPLY: multiply,
        CalculationType.DIVIDE: divide,
    }

    @classmethod
    def supported_types(cls) -> List[CalculationType]:
        return list(cls._OPERATIONS)

    @staticmethod
    def _resolve(calc_type) -> CalculationType:
        if isinstance(calc_type, CalculationType):
            return calc_type
        try:
            return CalculationType(normalise_type_name(calc_type))
        except ValueError:
            raise ValueError(f"Unsupported calculation type: {calc_type!r}") from None

    @classmethod
    def get_operation(cls, calc_type) -> Operation:
        return cls._OPERATIONS[cls._resolve(calc_type)]

    @classmethod
    def compute(cls, calc_type, a: float, b: float) -> float:
        return cls.get_operation(calc_type)(a, b)

    @classmethod
    def create(
        cls, calc_type, a: float, b: float, user_id: Optional[UUID] = None
    ) -> Calculation:
        resolved = cls._resolve(calc_type)
        return Calculation(
            a=a,
            b=b,
            type=resolved.value,
            result=cls._OPERATIONS[resolved](a, b),
            user_id=user_id,
        )

    @classmethod
    def from_schema(cls, data: CalculationCreate) -> Calculation:
        return cls.create(data.type, data.a, data.b, user_id=data.user_id)