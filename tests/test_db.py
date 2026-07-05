import os

import pytest

from sp_worker.db import check_connection

TEST_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgres://kontent:kontent@localhost:5432/kontentmaschine_test"
)


def test_check_connection_returns_server_version():
    version = check_connection(TEST_URL)
    assert version.startswith("PostgreSQL")


def test_check_connection_raises_on_bad_url():
    with pytest.raises(Exception):
        check_connection("postgres://nobody:wrong@localhost:5432/nope")


def test_check_connection_raises_runtime_error_not_assert(monkeypatch):
    import sp_worker.db as dbmod

    class FakeCursor:
        def execute(self, q):
            pass

        def fetchone(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(dbmod.psycopg, "connect", lambda *a, **k: FakeConn())
    with pytest.raises(RuntimeError):
        dbmod.check_connection("postgres://x")
