import pytest

from sp_worker import repo
from sp_worker.stages.research import Finding, fetch_research
from .test_repo import FINDING, _mk_series


def test_returns_none_for_series_without_knowledge_source(conn):
    series_id = _mk_series(conn)  # knowledge_source defaults to 'none'
    series = repo.fetch_series(conn, series_id)
    assert fetch_research(conn, series) is None


def test_returns_oldest_unused_finding_for_consensus_series(conn):
    series_id = _mk_series(conn)
    with conn.cursor() as cur:
        cur.execute("UPDATE series SET knowledge_source = 'consensus' WHERE id = %s", (series_id,))
    conn.commit()
    repo.insert_finding(conn, series_id, FINDING)
    series = repo.fetch_series(conn, series_id)
    f = fetch_research(conn, series)
    assert isinstance(f, Finding)
    assert f.topic == "The spotlight effect"
    assert f.paper_url.startswith("https://")


def test_raises_actionable_error_when_bank_empty(conn):
    series_id = _mk_series(conn)
    with conn.cursor() as cur:
        cur.execute("UPDATE series SET knowledge_source = 'consensus' WHERE id = %s", (series_id,))
    conn.commit()
    series = repo.fetch_series(conn, series_id)
    with pytest.raises(ValueError, match="research bank empty"):
        fetch_research(conn, series)
