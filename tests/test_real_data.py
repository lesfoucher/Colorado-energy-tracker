"""Spot checks against the real database, using the reference numbers in docs/requirements.md.

Skipped if the pipeline hasn't been run yet. The EIA revises recent months, so the tolerances
allow small changes without letting a real error through.
"""
import pytest

from pipeline import load

pytestmark = pytest.mark.skipif(not load.DB_PATH.exists(), reason="run `python -m pipeline.run` first")


@pytest.fixture(scope="module")
def con():
    c = load.connect()
    yield c
    c.close()


def value(con, sql):
    return con.execute(sql).fetchone()[0]


def test_history_starts_in_2001(con):
    assert value(con, "SELECT MIN(period) FROM v_mix") == "2001-01"


def test_no_missing_months(con):
    first, last, n = con.execute("SELECT MIN(period), MAX(period), COUNT(*) FROM v_mix").fetchone()
    expected = (int(last[:4]) - int(first[:4])) * 12 + int(last[5:]) - int(first[5:]) + 1
    assert n == expected


def test_july_2026_reference_numbers(con):
    r = con.execute("SELECT * FROM v_mix_yoy WHERE period = '2026-07'").fetchone()
    assert r["total_gwh"] == pytest.approx(5701.9, rel=0.01)
    assert r["renewable_share_pct"] == pytest.approx(45.9, abs=0.5)
    assert r["coal_change_pct"] == pytest.approx(-35.6, abs=1.0)
    assert value(con, "SELECT price_cents_kwh FROM v_price WHERE period = '2026-07' AND sector = 'RES'") \
        == pytest.approx(17.0, abs=0.2)
