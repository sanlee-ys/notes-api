"""Tests for the per-request session dependency.

The conftest ``client`` fixture overrides ``get_db`` for every route test, so
the real dependency's open/yield/close lifecycle is never exercised there.
These tests drive the generator directly with a stand-in session factory.
"""

import pytest

from notes_api import database


class _FakeSession:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def sessions(monkeypatch):
    """Patch SessionLocal and record every session it hands out."""
    made = []

    def _factory():
        made.append(_FakeSession())
        return made[-1]

    monkeypatch.setattr(database, "SessionLocal", _factory)
    return made


class TestGetDb:
    def test_yields_an_open_session(self, sessions):
        gen = database.get_db()
        session = next(gen)
        assert session is sessions[0]
        assert session.closed is False

    def test_closes_the_session_when_the_request_finishes(self, sessions):
        gen = database.get_db()
        next(gen)
        with pytest.raises(StopIteration):
            next(gen)
        assert sessions[0].closed is True

    def test_closes_the_session_when_the_handler_raises(self, sessions):
        gen = database.get_db()
        next(gen)
        with pytest.raises(RuntimeError):
            gen.throw(RuntimeError("handler blew up"))
        assert sessions[0].closed is True

    def test_each_request_gets_its_own_session(self, sessions):
        first = next(database.get_db())
        second = next(database.get_db())
        assert first is not second
        assert len(sessions) == 2
