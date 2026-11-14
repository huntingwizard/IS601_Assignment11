"""
Integration tests: Calculation rows against a real Postgres database.
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.factory import CalculationFactory
from app.models.calculation import Calculation
from app.models.user import User
from app.schemas import CalculationCreate, CalculationRead, CalculationType


def save(session, *rows):
    session.add_all(rows)
    session.commit()


def assert_rejected(session):
    """Commit must fail with an IntegrityError; leave the session usable."""
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def raw_row(**overrides) -> Calculation:
    fields = {"a": 1.0, "b": 2.0, "type": "add", "result": 3.0}
    fields.update(overrides)
    return Calculation(**fields)


# --------------------------------------------------------------------------
# Saving and reading back
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "calc_type, a, b, expected",
    [("add", 2, 3, 5), ("subtract", 9, 4, 5), ("multiply", 6, 7, 42), ("divide", 8, 2, 4)],
)
def test_factory_built_row_is_stored_correctly(session, owner, calc_type, a, b, expected):
    row = CalculationFactory.create(calc_type, a, b, user_id=owner.id)
    save(session, row)

    stored = session.get(Calculation, row.id)

    assert (stored.a, stored.b) == (a, b)
    assert stored.type == calc_type
    assert stored.result == pytest.approx(expected)


def test_saved_row_gets_id_and_timestamp(session, owner):
    row = CalculationFactory.create("add", 1, 2, user_id=owner.id)
    save(session, row)
    session.refresh(row)

    assert isinstance(row.id, uuid.UUID)
    assert isinstance(row.created_at, datetime)


def test_fractional_values_survive_a_round_trip(session):
    row = CalculationFactory.create("add", 0.1, 0.2)
    save(session, row)
    session.expire_all()

    stored = session.get(Calculation, row.id)

    assert stored.result == pytest.approx(0.3)


def test_rows_can_be_filtered_by_type(session):
    save(
        session,
        CalculationFactory.create("add", 1, 1),
        CalculationFactory.create("add", 2, 2),
        CalculationFactory.create("divide", 4, 2),
    )

    assert session.query(Calculation).filter_by(type="add").count() == 2
    assert session.query(Calculation).filter_by(type="divide").count() == 1


# --------------------------------------------------------------------------
# Relationship with users
# --------------------------------------------------------------------------

def test_calculation_belongs_to_its_owner(session, owner):
    row = CalculationFactory.create("add", 1, 2, user_id=owner.id)
    save(session, row)
    session.refresh(owner)

    assert row.user is owner
    assert [c.id for c in owner.calculations] == [row.id]


def test_calculation_without_owner_is_allowed(session):
    row = CalculationFactory.create("add", 1, 2)
    save(session, row)

    assert session.get(Calculation, row.id).user is None


def test_unknown_owner_is_rejected(session):
    session.add(CalculationFactory.create("add", 1, 2, user_id=uuid.uuid4()))

    assert_rejected(session)


def test_deleting_a_user_deletes_their_calculations(session, owner):
    save(
        session,
        CalculationFactory.create("add", 1, 2, user_id=owner.id),
        CalculationFactory.create("multiply", 3, 4, user_id=owner.id),
    )

    session.delete(owner)
    session.commit()

    assert session.query(Calculation).count() == 0
    assert session.query(User).count() == 0


# --------------------------------------------------------------------------
# Rules enforced by the database
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad_type", ["power", "ADD", "", "addition"])
def test_database_rejects_unknown_types(session, bad_type):
    session.add(raw_row(type=bad_type))

    assert_rejected(session)


def test_database_rejects_a_zero_divisor(session):
    session.add(raw_row(type="divide", a=10, b=0, result=None))

    assert_rejected(session)


def test_database_allows_zero_where_it_is_harmless(session):
    save(
        session,
        raw_row(type="divide", a=0, b=5, result=0),
        raw_row(type="add", a=5, b=0, result=5),
        raw_row(type="multiply", a=5, b=0, result=0),
    )

    assert session.query(Calculation).count() == 3


@pytest.mark.parametrize("column", ["a", "b", "type"])
def test_required_columns_cannot_be_null(session, column):
    session.add(raw_row(**{column: None}))

    assert_rejected(session)


def test_session_still_works_after_a_rejected_row(session):
    session.add(raw_row(type="power"))
    assert_rejected(session)

    save(session, raw_row())

    assert session.query(Calculation).count() == 1


# --------------------------------------------------------------------------
# Schemas and database together
# --------------------------------------------------------------------------

def test_create_schema_to_row_to_read_schema(session, owner):
    payload = CalculationCreate(a=9, b=3, type="Divide", user_id=owner.id)

    row = CalculationFactory.from_schema(payload)
    save(session, row)
    session.expire_all()
    read = CalculationRead.model_validate(session.get(Calculation, row.id))

    assert read.type is CalculationType.DIVIDE
    assert (read.a, read.b, read.result) == (9, 3, 3)
    assert read.user_id == owner.id


def test_read_schema_leaves_out_owner_details(session, owner):
    row = CalculationFactory.create("add", 1, 2, user_id=owner.id)
    save(session, row)

    dumped = CalculationRead.model_validate(row).model_dump()

    assert "user" not in dumped
    assert "email" not in dumped and "username" not in dumped

def test_user_can_own_many_calculations(session, owner):
    save(
        session,
        *(CalculationFactory.create("add", n, n, user_id=owner.id) for n in (1, 2, 3)),
    )
    session.refresh(owner)

    assert sorted(c.a for c in owner.calculations) == [1, 2, 3]


@pytest.mark.parametrize("a, b", [(-5.5, -2.25), (1e12, 1e-6), (0, 0)])
def test_unusual_values_round_trip(session, a, b):
    row = CalculationFactory.create("add", a, b)
    save(session, row)
    session.expire_all()

    stored = session.get(Calculation, row.id)

    assert (stored.a, stored.b) == (a, b)
    assert stored.result == pytest.approx(a + b)