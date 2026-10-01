"""Export the metric views to the files the dashboard reads: site/data.json and a CSV download."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline import load

SITE = load.ROOT / "site"
DATA_JSON = SITE / "data.json"
CSV_PATH = SITE / "colorado-electricity-monthly.csv"
SECTORS = {"RES": "Residential", "COM": "Commercial", "IND": "Industrial", "ALL": "All sectors"}


def rows(con, sql, *args):
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def r1(x, digits=1):
    return None if x is None else round(x, digits)


def build(con):
    latest = con.execute("SELECT MAX(period) FROM v_mix_yoy").fetchone()[0]
    yoy = rows(con, "SELECT * FROM v_mix_yoy WHERE period = ?", latest)[0]
    prices = {r["sector"]: r for r in rows(con, "SELECT * FROM v_price WHERE period = ?", latest)}

    monthly = rows(con, """
        SELECT m.*, t.renewable_share_12m_pct, c.coal_rolling_12m_gwh,
               pr.price AS res_price, pc.price AS com_price, pi.price AS ind_price, pa.price AS all_price
        FROM v_mix m
        JOIN v_renewable_trend t USING (period)
        JOIN v_coal_trend c USING (period)
        LEFT JOIN retail pr ON pr.period = m.period AND pr.sector = 'RES'
        LEFT JOIN retail pc ON pc.period = m.period AND pc.sector = 'COM'
        LEFT JOIN retail pi ON pi.period = m.period AND pi.sector = 'IND'
        LEFT JOIN retail pa ON pa.period = m.period AND pa.sector = 'ALL'
        ORDER BY m.period""")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "latest_period": latest,
        "prior_period": yoy["prior_period"],
        "headline": {
            "renewable_share_pct": r1(yoy["renewable_share_pct"]),
            "renewable_share_change_pp": r1(yoy["renewable_share_change_pp"]),
            "total_gwh": r1(yoy["total_gwh"]),
            "total_change_pct": r1(yoy["total_change_pct"]),
            "coal_gwh": r1(yoy["coal_gwh"]),
            "coal_change_pct": r1(yoy["coal_change_pct"]),
            "res_price": r1(prices["RES"]["price_cents_kwh"], 2),
            "res_price_change_pct": r1(prices["RES"]["price_change_pct"]),
        },
        "annual": [{k: (v if k == "year" else r1(v)) for k, v in r.items()}
                   for r in rows(con, "SELECT * FROM v_annual_mix ORDER BY year")],
        "monthly": [{
            "period": r["period"],
            "total": r1(r["total_gwh"]), "coal": r1(r["coal_gwh"]), "gas": r1(r["gas_gwh"]),
            "wind": r1(r["wind_gwh"]), "solar": r1(r["solar_gwh"]), "hydro": r1(r["hydro_gwh"]),
            "other": r1(r["other_gwh"]), "rooftop_solar": r1(r["rooftop_solar_gwh"]),
            "renewable_share": r1(r["renewable_share_pct"]),
            "renewable_share_12m": r1(r["renewable_share_12m_pct"]),
            "coal_12m": r1(r["coal_rolling_12m_gwh"]),
            "price_res": r["res_price"], "price_com": r["com_price"],
            "price_ind": r["ind_price"], "price_all": r["all_price"],
        } for r in monthly],
    }


CSV_COLUMNS = [
    ("period", "Month"), ("total", "Total generation (GWh)"), ("coal", "Coal (GWh)"), ("gas", "Natural gas (GWh)"),
    ("wind", "Wind (GWh)"), ("solar", "Utility solar (GWh)"), ("hydro", "Hydro (GWh)"), ("other", "Other (GWh)"),
    ("rooftop_solar", "Rooftop solar, EIA estimate (GWh)"), ("renewable_share", "Renewable share (%)"),
    ("price_res", "Residential price (cents/kWh)"), ("price_com", "Commercial price (cents/kWh)"),
    ("price_ind", "Industrial price (cents/kWh)"), ("price_all", "All-sector price (cents/kWh)"),
]


def main():
    con = load.connect()
    data = build(con)
    con.close()
    SITE.mkdir(exist_ok=True)
    DATA_JSON.write_text(json.dumps(data, separators=(",", ":")))
    with CSV_PATH.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([label for _, label in CSV_COLUMNS])
        for m in data["monthly"]:
            w.writerow(["" if m[k] is None else m[k] for k, _ in CSV_COLUMNS])
    print(f"Exported {len(data['monthly'])} months through {data['latest_period']} to site/")


if __name__ == "__main__":
    main()
