"""Unit tests for the calculation schemas (no database needed)."""

import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas import CalculationCreate, CalculationRead, CalculationType


def failing_fields(exc_info) -> set:
    """Names of the fields a ValidationError complains about."""
    return {e["loc"][0] if e["loc"] else "__model__" for e in exc_info.value.errors()}


# --------------------------------------------------------------------------
# CalculationCreate: valid input
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["add", "subtract", "multiply", "divide"])
def test_each_operation_is_accepted(name):
    data = CalculationCreate(a=8, b=2, type=name)

    assert data.type == CalculationType(name)
    assert (data.a, data.b) == (8.0, 2.0)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("ADD", CalculationType.ADD),
        ("  Multiply ", CalculationType.MULTIPLY),
        ("DiViDe", CalculationType.DIVIDE),
        ("Sub", CalculationType.SUBTRACT),
    ],
)
def test_type_is_case_and_whitespace_insensitive(raw, expected):
    assert CalculationCreate(a=1, b=1, type=raw).type == expected


def test_numeric_strings_are_coerced_to_floats():
    data = CalculationCreate(a="5", b="2.5", type="add")

    assert (data.a, data.b) == (5.0, 2.5)


def test_user_id_is_optional():
    assert CalculationCreate(a=1, b=2, type="add").user_id is None


def test_user_id_is_parsed_when_given():
    owner = uuid.uuid4()

    assert CalculationCreate(a=1, b=2, type="add", user_id=str(owner)).user_id == owner


def test_zero_is_fine_outside_the_divisor():
    CalculationCreate(a=0, b=5, type="divide")
    CalculationCreate(a=5, b=0, type="add")
    CalculationCreate(a=5, b=0, type="multiply")


# --------------------------------------------------------------------------
# CalculationCreate: invalid input
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad_type", ["power", "", "addition", 42, None])
def test_unknown_type_is_rejected(bad_type):
    with pytest.raises(ValidationError) as caught:
        CalculationCreate(a=1, b=2, type=bad_type)

    assert failing_fields(caught) == {"type"}


@pytest.mark.parametrize("zero", [0, 0.0, -0.0, "0"])
def test_zero_divisor_is_rejected(zero):
    with pytest.raises(ValidationError, match="Cannot divide by zero"):
        CalculationCreate(a=10, b=zero, type="divide")


@pytest.mark.parametrize("field", ["a", "b"])
def test_non_numeric_operand_is_rejected(field):
    values = {"a": 1, "b": 2, "type": "add", field: "abc"}

    with pytest.raises(ValidationError) as caught:
        CalculationCreate(**values)

    assert failing_fields(caught) == {field}


@pytest.mark.parametrize("bad", [float("inf"), float("-inf"), float("nan")])
def test_infinity_and_nan_are_rejected(bad):
    with pytest.raises(ValidationError) as caught:
        CalculationCreate(a=bad, b=1, type="add")

    assert failing_fields(caught) == {"a"}


@pytest.mark.parametrize("missing", ["a", "b", "type"])
def test_required_fields_must_be_present(missing):
    values = {"a": 1, "b": 2, "type": "add"}
    del values[missing]

    with pytest.raises(ValidationError) as caught:
        CalculationCreate(**values)

    assert failing_fields(caught) == {missing}


def test_malformed_user_id_is_rejected():
    with pytest.raises(ValidationError) as caught:
        CalculationCreate(a=1, b=2, type="add", user_id="not-a-uuid")

    assert failing_fields(caught) == {"user_id"}


# --------------------------------------------------------------------------
# CalculationRead
# --------------------------------------------------------------------------

def stored_row(**overrides):
    row = {
        "id": uuid.uuid4(),
        "a": 6.0,
        "b": 3.0,
        "type": "divide",
        "result": 2.0,
        "user_id": uuid.uuid4(),
        "created_at": datetime(2026, 1, 1, 9, 30),
    }
    row.update(overrides)
    return row


def test_read_schema_serialises_an_object():
    row = stored_row()

    read = CalculationRead.model_validate(SimpleNamespace(**row))

    assert read.id == row["id"]
    assert read.type is CalculationType.DIVIDE
    assert read.result == 2.0


def test_read_schema_exposes_only_calculation_fields():
    assert set(CalculationRead.model_fields) == {
        "id", "a", "b", "type", "result", "user_id", "created_at",
    }


def test_read_schema_allows_missing_result_and_owner():
    read = CalculationRead(**stored_row(result=None, user_id=None))

    assert read.result is None and read.user_id is None


def test_read_schema_rejects_unknown_type():
    with pytest.raises(ValidationError) as caught:
        CalculationRead(**stored_row(type="power"))

    assert failing_fields(caught) == {"type"}