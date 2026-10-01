"""Turn raw EIA rows into clean, typed records and check that they add up."""
import re
from collections import defaultdict

PERIOD = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
SECTORS = {"ALL", "RES", "COM", "IND"}  # transportation and "other" are excluded; see requirements
MIX_FUELS = ["COW", "NG", "WND", "SUN", "HYC"]
TOLERANCE_GWH = 0.1


class DataQualityError(Exception):
    pass


def to_number(value, field, row):
    """Convert the API's text values to floats. Missing stays None; anything unparseable is an error."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise DataQualityError(f"Could not convert {field}={value!r} to a number in row {row}")


def check_period(period, row):
    if not isinstance(period, str) or not PERIOD.match(period):
        raise DataQualityError(f"Unexpected period {period!r} in row {row}")


def clean_generation(rows):
    """Return [(period, fuel, gwh)]. EIA reports thousand MWh, which is the same as GWh."""
    records = []
    for row in rows:
        check_period(row["period"], row)
        if row.get("generation-units") not in (None, "thousand megawatthours"):
            raise DataQualityError(f"Unexpected generation units in row {row}")
        gwh = to_number(row.get("generation"), "generation", row)
        if gwh is None:
            continue  # no data for this fuel this month: stored as missing, not zero
        records.append((row["period"], row["fueltypeid"], gwh))
    return records


def clean_retail(rows):
    """Return [(period, sector, price_cents_per_kwh, sales_gwh, customers)]."""
    records = []
    for row in rows:
        if row["sectorid"] not in SECTORS:
            continue
        check_period(row["period"], row)
        records.append((
            row["period"],
            row["sectorid"],
            to_number(row.get("price"), "price", row),
            to_number(row.get("sales"), "sales", row),  # million kWh, which is the same as GWh
            to_number(row.get("customers"), "customers", row),
        ))
    return records


def check_generation(records):
    """Stop the run if the totals don't add up. Returns the number of months checked."""
    by_month = defaultdict(dict)
    for period, fuel, gwh in records:
        if fuel in by_month[period]:
            raise DataQualityError(f"Duplicate row for {fuel} in {period}")
        by_month[period][fuel] = gwh

    for period, fuels in by_month.items():
        if "ALL" not in fuels:
            raise DataQualityError(f"{period}: total generation (ALL) is missing")
        other = fuels["ALL"] - sum(fuels.get(f, 0.0) for f in MIX_FUELS)
        if abs(other) > 0.02 * fuels["ALL"]:
            raise DataQualityError(f"{period}: 'Other' is {other:.1f} GWh, more than 2% of the total")
        if "REN" in fuels:
            renewable = fuels.get("AOR", 0.0) + fuels.get("HYC", 0.0)
            if abs(fuels["REN"] - renewable) > TOLERANCE_GWH:
                raise DataQualityError(
                    f"{period}: REN ({fuels['REN']:.1f}) does not equal AOR + HYC ({renewable:.1f})")
    return len(by_month)


def clean_profile(rows):
    """Return {year: total GWh} from the EIA state profile (reported in MWh)."""
    totals = {}
    for row in rows:
        if row.get("total-net-generation-units") != "megawatthours":
            raise DataQualityError(f"Unexpected state profile units in row {row}")
        totals[row["period"]] = to_number(row["total-net-generation"], "total-net-generation", row) / 1000
    return totals


def check_against_profile(annual_totals, profile_totals, tolerance_pct=0.5):
    """Compare complete-year totals from the monthly data with the EIA's published annual totals.
    Returns the number of years compared."""
    years = sorted(set(annual_totals) & set(profile_totals))
    if not years:
        raise DataQualityError("No overlapping years with the EIA state profile to check against")
    for year in years:
        diff_pct = 100 * (annual_totals[year] - profile_totals[year]) / profile_totals[year]
        if abs(diff_pct) > tolerance_pct:
            raise DataQualityError(
                f"{year}: monthly data sums to {annual_totals[year]:,.1f} GWh but the EIA state profile "
                f"reports {profile_totals[year]:,.1f} GWh ({diff_pct:+.2f}%)")
    return len(years)
