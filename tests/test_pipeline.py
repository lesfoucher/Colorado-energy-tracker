"""Tests for cleaning, data checks, and the SQL metric views.

These use small hand-made datasets where the right answer is known, so they run offline.
"""
import pytest

from pipeline import clean, load


def gen_row(period, fuel, value):
    return {"period": period, "fueltypeid": fuel, "generation": value, "generation-units": "thousand megawatthours"}


def month(period, coal, gas, wind, solar, hydro, other=0.0, rooftop=None):
    """Build one month of clean generation records that satisfies the EIA's own identities."""
    total = coal + gas + wind + solar + hydro + other
    aor = wind + solar
    records = [(period, "ALL", total), (period, "COW", coal), (period, "NG", gas), (period, "WND", wind),
               (period, "SUN", solar), (period, "HYC", hydro), (period, "AOR", aor), (period, "REN", aor + hydro)]
    if rooftop is not None:
        records.append((period, "DPV", rooftop))
    return records


# ---- Cleaning ----

def test_clean_generation_converts_text_to_numbers():
    assert clean.clean_generation([gen_row("2026-07", "ALL", "5701.90972")]) == [("2026-07", "ALL", 5701.90972)]


def test_missing_values_are_skipped_not_zeroed():
    assert clean.clean_generation([gen_row("2001-01", "SUN", None)]) == []


def test_negative_values_are_kept():
    # Pumped storage can use more power than it produces.
    assert clean.clean_generation([gen_row("2026-07", "OTH", "-2.009")])[0][2] == -2.009


def test_unparseable_number_stops_the_run():
    with pytest.raises(clean.DataQualityError):
        clean.clean_generation([gen_row("2026-07", "ALL", "n/a")])


def test_bad_period_stops_the_run():
    with pytest.raises(clean.DataQualityError):
        clean.clean_generation([gen_row("2026-13", "ALL", "1")])


def test_unexpected_units_stop_the_run():
    row = gen_row("2026-07", "ALL", "1")
    row["generation-units"] = "megawatthours"
    with pytest.raises(clean.DataQualityError):
        clean.clean_generation([row])


def test_retail_excludes_transportation_and_other():
    rows = [{"period": "2026-07", "sectorid": s, "price": "10", "sales": "1", "customers": "1"}
            for s in ["ALL", "RES", "COM", "IND", "TRA", "OTH"]]
    assert {r[1] for r in clean.clean_retail(rows)} == {"ALL", "RES", "COM", "IND"}


# ---- Data checks ----

def test_consistent_data_passes():
    assert clean.check_generation(month("2026-07", 100, 200, 150, 90, 20)) == 1


def test_renewable_mismatch_stops_the_run():
    records = month("2026-07", 100, 200, 150, 90, 20)
    records = [(p, f, v + 5 if f == "REN" else v) for p, f, v in records]
    with pytest.raises(clean.DataQualityError, match="REN"):
        clean.check_generation(records)


def test_sources_not_adding_up_stops_the_run():
    records = month("2026-07", 100, 200, 150, 90, 20)
    records = [(p, f, v * 2 if f == "ALL" else v) for p, f, v in records]
    with pytest.raises(clean.DataQualityError, match="Other"):
        clean.check_generation(records)


def test_duplicate_rows_stop_the_run():
    records = month("2026-07", 100, 200, 150, 90, 20)
    with pytest.raises(clean.DataQualityError, match="Duplicate"):
        clean.check_generation(records + records[:1])


def test_missing_total_stops_the_run():
    records = [r for r in month("2026-07", 100, 200, 150, 90, 20) if r[1] != "ALL"]
    with pytest.raises(clean.DataQualityError, match="ALL"):
        clean.check_generation(records)


def test_profile_check_catches_a_mismatch():
    with pytest.raises(clean.DataQualityError, match="2024"):
        clean.check_against_profile({"2024": 100.0}, {"2024": 102.0})


def test_profile_check_passes_within_tolerance():
    assert clean.check_against_profile({"2024": 100.0, "2025": 50.0}, {"2024": 100.1}) == 1


# ---- SQL metrics ----

@pytest.fixture
def db(tmp_path):
    """Two full years (2024-2025) plus July 2026, with simple round numbers."""
    generation = []
    for year in (2024, 2025):
        for m in range(1, 13):
            coal = 100.0 if year == 2024 else 60.0
            generation += month(f"{year}-{m:02d}", coal=coal, gas=200, wind=150, solar=40, hydro=10, other=0)
    generation += month("2026-07", coal=30, gas=200, wind=200, solar=60, hydro=10, other=0, rooftop=25)
    retail = [("2025-07", "RES", 16.0, 2500, 2_500_000), ("2026-07", "RES", 17.0, 2600, 2_550_000)]
    path = load.build_database(generation, retail, tmp_path / "test.db")
    con = load.connect(path)
    yield con
    con.close()


def one(con, sql, *args):
    return con.execute(sql, args).fetchone()


def test_mix_adds_up_to_total(db):
    r = one(db, "SELECT * FROM v_mix WHERE period = '2026-07'")
    parts = r["coal_gwh"] + r["gas_gwh"] + r["wind_gwh"] + r["solar_gwh"] + r["hydro_gwh"] + r["other_gwh"]
    assert parts == pytest.approx(r["total_gwh"])


def test_renewable_share_includes_hydro(db):
    # Jul 2026: (wind 200 + solar 60 + hydro 10) / total 500 = 54%
    assert one(db, "SELECT renewable_share_pct FROM v_mix WHERE period = '2026-07'")[0] == pytest.approx(54.0)


def test_rooftop_solar_is_not_in_the_total(db):
    r = one(db, "SELECT total_gwh, rooftop_solar_gwh FROM v_mix WHERE period = '2026-07'")
    assert (r["total_gwh"], r["rooftop_solar_gwh"]) == (500.0, 25.0)


def test_year_over_year_uses_same_month_last_year(db):
    r = one(db, "SELECT * FROM v_mix_yoy WHERE period = '2026-07'")
    assert r["prior_period"] == "2025-07"
    assert r["coal_change_pct"] == pytest.approx(-50.0)  # 60 -> 30
    # Jul 2025 share = 200 / 460 = 43.48%; Jul 2026 = 54%; change in percentage points
    assert r["renewable_share_change_pp"] == pytest.approx(54.0 - 100 * 200 / 460)


def test_no_year_over_year_without_prior_year(db):
    assert one(db, "SELECT COUNT(*) FROM v_mix_yoy WHERE period LIKE '2024-%'")[0] == 0


def test_rolling_coal_needs_twelve_months(db):
    rows = db.execute("SELECT period, coal_rolling_12m_gwh FROM v_coal_trend ORDER BY period").fetchall()
    assert rows[10]["coal_rolling_12m_gwh"] is None           # Nov 2024: only 11 months
    assert rows[11]["coal_rolling_12m_gwh"] == pytest.approx(1200)  # Dec 2024: 12 x 100
    assert rows[23]["coal_rolling_12m_gwh"] == pytest.approx(720)   # Dec 2025: 12 x 60


def test_annual_mix_only_includes_complete_years(db):
    years = [r[0] for r in db.execute("SELECT year FROM v_annual_mix ORDER BY year")]
    assert years == ["2024", "2025"]


def test_price_change(db):
    r = one(db, "SELECT * FROM v_price WHERE period = '2026-07' AND sector = 'RES'")
    assert r["price_cents_kwh"] == 17.0
    assert r["price_change_pct"] == pytest.approx(6.25)
