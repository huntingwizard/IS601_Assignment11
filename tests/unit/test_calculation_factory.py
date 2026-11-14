"""Unit tests for CalculationFactory (no database needed)."""

import uuid

import pytest

from app.factory import CalculationFactory
from app.models.calculation import Calculation
from app.operations import add, divide, multiply, subtract
from app.schemas import CalculationCreate, CalculationType


# --------------------------------------------------------------------------
# Choosing and running operations
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "calc_type, a, b, expected",
    [
        ("add", 2, 3, 5),
        ("add", -1.5, 0.5, -1.0),
        ("subtract", 10, 4, 6),
        ("subtract", 1, 5, -4),
        ("multiply", 6, 7, 42),
        ("multiply", -2, 0, 0),
        ("divide", 9, 3, 3),
        ("divide", 1, 4, 0.25),
    ],
)
def test_compute_returns_expected_value(calc_type, a, b, expected):
    assert CalculationFactory.compute(calc_type, a, b) == pytest.approx(expected)


@pytest.mark.parametrize(
    "calc_type, function",
    [("add", add), ("subtract", subtract), ("multiply", multiply), ("divide", divide)],
)
def test_factory_picks_the_matching_operation(calc_type, function):
    assert CalculationFactory.get_operation(calc_type) is function


def test_factory_accepts_enum_members():
    assert CalculationFactory.get_operation(CalculationType.MULTIPLY) is multiply


@pytest.mark.parametrize(
    "raw, function",
    [("ADD", add), ("  Add ", add), ("sub", subtract), ("DiVidE", divide)],
)
def test_type_lookup_is_forgiving(raw, function):
    assert CalculationFactory.get_operation(raw) is function


@pytest.mark.parametrize("bad", ["power", "", "modulus", None, 42])
def test_unsupported_type_is_rejected(bad):
    with pytest.raises(ValueError, match="Unsupported calculation type"):
        CalculationFactory.get_operation(bad)


def test_every_schema_type_has_an_operation():
    assert set(CalculationFactory.supported_types()) == set(CalculationType)


def test_dividing_by_zero_raises():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        CalculationFactory.compute("divide", 5, 0)


# --------------------------------------------------------------------------
# Building Calculation rows
# --------------------------------------------------------------------------

def test_create_builds_row_with_result_filled_in():
    owner = uuid.uuid4()

    row = CalculationFactory.create("multiply", 6, 7, user_id=owner)

    assert isinstance(row, Calculation)
    assert (row.a, row.b) == (6, 7)
    assert row.type == "multiply"
    assert row.result == 42
    assert row.user_id == owner


def test_create_normalises_the_type_string():
    assert CalculationFactory.create("ADD", 1, 2).type == "add"


def test_create_without_owner_leaves_user_id_empty():
    assert CalculationFactory.create("add", 1, 2).user_id is None


def test_create_propagates_division_by_zero():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        CalculationFactory.create("divide", 1, 0)


def test_create_rejects_unknown_type():
    with pytest.raises(ValueError, match="Unsupported calculation type"):
        CalculationFactory.create("power", 2, 3)


def test_from_schema_copies_every_field():
    owner = uuid.uuid4()
    payload = CalculationCreate(a=8, b=2, type="Divide", user_id=owner)

    row = CalculationFactory.from_schema(payload)

    assert (row.a, row.b, row.type, row.result) == (8, 2, "divide", 4)
    assert row.user_id == owner
def test_repr_shows_operands_type_and_result():
    row = CalculationFactory.create("multiply", 6.0, 7.0)

    assert repr(row) == "<Calculation(6.0 multiply 7.0 = 42.0)>"