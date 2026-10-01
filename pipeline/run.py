"""Run the pipeline: fetch -> clean -> check -> load.

    python -m pipeline.run            # download fresh data from the EIA
    python -m pipeline.run --offline  # rebuild from the saved raw responses
"""
import argparse

from pipeline import clean, fetch, load


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="use saved raw data instead of calling the API")
    args = parser.parse_args()

    # Every run rebuilds from the full history, so the EIA's revisions to recent months are always picked up.
    raw = fetch.load_raw() if args.offline else fetch.fetch_all()
    generation = clean.clean_generation(raw["generation"])
    retail = clean.clean_retail(raw["retail"])
    months = clean.check_generation(generation)
    print(f"Data checks passed for {months} months")

    db = load.build_database(generation, retail)
    con = load.connect(db)
    first, last = con.execute("SELECT MIN(period), MAX(period) FROM v_mix").fetchone()
    annual = dict(con.execute("SELECT year, total_gwh FROM v_annual_mix").fetchall())
    con.close()

    years = clean.check_against_profile(annual, clean.clean_profile(raw["profile"]))
    print(f"Annual totals match the EIA's published state profile for {years} years")
    print(f"Built {db.relative_to(load.ROOT)}: {first} to {last}")


if __name__ == "__main__":
    main()
