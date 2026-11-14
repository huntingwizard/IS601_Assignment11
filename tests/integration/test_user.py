"""
Integration tests for the User model against a real Postgres database.

Uses the `db_session` fixture from conftest.py, which cleans all tables
after every test, so each test starts with an empty `users` table.
"""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.user import User

# bcrypt is deliberately slow, so hash once and reuse it for every test user.
SAMPLE_PASSWORD = "Sup3rSecret!"
SAMPLE_HASH = User.hash_password(SAMPLE_PASSWORD)


def build_user(n: int = 1, **overrides) -> User:
    """Build an unsaved User with unique, predictable values."""
    fields = {
        "first_name": f"First{n}",
        "last_name": f"Last{n}",
        "email": f"user{n}@example.com",
        "username": f"user_{n}",
        "password_hash": SAMPLE_HASH,
    }
    fields.update(overrides)
    return User(**fields)


def save(session, *users: User) -> None:
    session.add_all(users)
    session.commit()


# --------------------------------------------------------------------------
# Connectivity
# --------------------------------------------------------------------------

def test_can_query_database(db_session):
    assert db_session.execute(text("SELECT 1")).scalar() == 1


def test_users_table_starts_empty(db_session):
    assert db_session.query(User).count() == 0


# --------------------------------------------------------------------------
# Creating users
# --------------------------------------------------------------------------

def test_saved_user_gets_defaults(db_session):
    user = build_user()
    save(db_session, user)
    db_session.refresh(user)

    assert isinstance(user.id, uuid.UUID)
    assert user.is_active is True
    assert user.is_verified is False
    assert user.last_login is None
    assert isinstance(user.created_at, datetime)
    assert isinstance(user.updated_at, datetime)


def test_password_is_stored_as_hash(db_session):
    user = build_user()
    save(db_session, user)

    stored = db_session.query(User).filter_by(id=user.id).one()
    assert stored.password_hash != SAMPLE_PASSWORD
    assert stored.verify_password(SAMPLE_PASSWORD) is True
    assert stored.verify_password("not-the-password") is False


def test_insert_several_users_at_once(db_session):
    users = [build_user(i) for i in range(1, 11)]
    save(db_session, *users)

    assert db_session.query(User).count() == 10


# --------------------------------------------------------------------------
# Constraints
# --------------------------------------------------------------------------

def test_duplicate_email_rejected(db_session):
    save(db_session, build_user(1))

    db_session.add(build_user(2, email="user1@example.com"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicate_username_rejected(db_session):
    save(db_session, build_user(1))

    db_session.add(build_user(2, username="user_1"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("missing_field", [
    "first_name", "last_name", "email", "username", "password_hash",
])
def test_required_fields_cannot_be_null(db_session, missing_field):
    db_session.add(build_user(**{missing_field: None}))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_original_user_survives_failed_insert(db_session):
    original = build_user(1)
    save(db_session, original)
    original_id = original.id

    db_session.add(build_user(2, email=original.email))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    survivors = db_session.query(User).all()
    assert len(survivors) == 1
    assert survivors[0].id == original_id
    assert survivors[0].username == "user_1"


def test_session_usable_after_rollback(db_session):
    save(db_session, build_user(1))

    db_session.add(build_user(2, username="user_1"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    save(db_session, build_user(3))
    emails = {u.email for u in db_session.query(User).all()}
    assert emails == {"user1@example.com", "user3@example.com"}


# --------------------------------------------------------------------------
# Querying
# --------------------------------------------------------------------------

def test_lookup_by_email_and_username(db_session):
    save(db_session, *(build_user(i) for i in range(1, 4)))

    by_email = db_session.query(User).filter_by(email="user2@example.com").one()
    by_username = db_session.query(User).filter_by(username="user_3").one()

    assert by_email.username == "user_2"
    assert by_username.email == "user3@example.com"


def test_lookup_missing_user_returns_none(db_session):
    assert db_session.query(User).filter_by(email="nobody@example.com").first() is None


def test_results_can_be_ordered(db_session):
    save(db_session, build_user(3), build_user(1), build_user(2))

    usernames = [u.username for u in db_session.query(User).order_by(User.username)]
    assert usernames == ["user_1", "user_2", "user_3"]


# --------------------------------------------------------------------------
# Updating and deleting
# --------------------------------------------------------------------------

def test_update_changes_field_and_updated_at(db_session, test_user):
    before = test_user.updated_at

    test_user.first_name = "Renamed"
    db_session.commit()
    db_session.refresh(test_user)

    assert test_user.first_name == "Renamed"
    assert test_user.updated_at > before


def test_delete_removes_user(db_session):
    user = build_user()
    save(db_session, user)

    db_session.delete(user)
    db_session.commit()

    assert db_session.query(User).count() == 0


# --------------------------------------------------------------------------
# Transactions
# --------------------------------------------------------------------------

def test_failed_statement_rolls_back_pending_user(db_session):
    db_session.add(build_user())
    with pytest.raises(Exception):
        db_session.execute(text("SELECT * FROM table_that_does_not_exist"))
    db_session.rollback()

    assert db_session.query(User).count() == 0


# --------------------------------------------------------------------------
# String representation
# --------------------------------------------------------------------------

def test_repr_contains_name_and_email():
    user = build_user(7)
    text_repr = repr(user)

    assert "First7 Last7" in text_repr
    assert "user7@example.com" in text_repr