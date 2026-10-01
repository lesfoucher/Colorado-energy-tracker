# Requirements — Colorado Energy Tracker

## Purpose

Give a clear, regularly updated picture of how Colorado's electricity is produced and what it costs, so that someone without an energy background can understand the trends in a few minutes.

## Audience

| Who | What they need |
|---|---|
| A general reader (resident, student, journalist) | The headline numbers and the direction things are moving, in plain language |
| An analyst or hiring manager | Clear metric definitions, the data source, and the ability to download the numbers |

## Questions the tracker answers

1. How is Colorado's electricity generated, and how is that mix changing?
2. What share comes from renewables, and how fast is it growing year over year?
3. How is coal generation declining as plants retire?
4. How are electricity prices changing for homes and businesses?
5. What changed in the latest month, in plain English?

## Data sources

Both come from the U.S. Energy Information Administration (EIA) API v2. Coverage was checked against the live API on 2026-09-30.

| Dataset | API route | Filters | Coverage |
|---|---|---|---|
| Generation by fuel | `electricity/electric-power-operational-data` | `location=CO`, `sectorid=99` (all sectors), monthly | Jan 2001 – Jul 2026 |
| Retail price | `electricity/retail-sales` | `stateid=CO`, monthly | Jan 2001 – Jul 2026 |

- **Units:** generation is reported in thousand megawatt-hours, which equals **gigawatt-hours (GWh)**. Prices are in **cents per kilowatt-hour**.
- **Data lag:** the EIA publishes monthly data about two to three months late. On 2026-09-30 the latest month is July 2026. The dashboard must always say which month the data runs through.
- **Revisions:** the EIA revises recent months after first publishing them. Each pipeline run re-fetches the most recent 24 months and replaces what's stored, instead of only adding new months.

## Metric definitions

### 1. Total generation
- **Definition:** all electricity generated in Colorado in the month, in GWh (`fueltypeid=ALL`).
- **Scope:** this covers power plants, not rooftop solar. The EIA estimates small-scale solar (`DPV`) separately from 2014 on. It is shown as its own line, not added into the total, because it's an estimate and isn't part of the EIA's official total.

### 2. Generation mix
The share of total generation from each source:

| Category | EIA code |
|---|---|
| Coal | `COW` (all coal products) |
| Natural gas | `NG` |
| Wind | `WND` |
| Solar (utility-scale) | `SUN` |
| Hydroelectric | `HYC` (conventional hydro) |
| Other | Total minus the five categories above |

"Other" is calculated as the remainder, so the mix always adds up to exactly 100%. It includes petroleum, biomass, pumped storage, and miscellaneous sources, which together have never been more than 0.85% of generation in any month since 2001.

### 3. Renewable share
- **Definition:** renewable generation ÷ total generation, where renewable generation = `AOR + HYC`.
- This covers wind, solar, hydro, and biomass.
- **Watch out:** the EIA's "all renewables" code (`AOR`) **leaves out hydro**, despite its name. The EIA's other renewables code (`REN`) includes hydro, but it's missing for 2001–2002. For every month where `REN` exists (2003 onward), it equals `AOR + HYC` exactly, so the tracker calculates `AOR + HYC` to cover the full history.
- Pumped storage is not counted as renewable. It stores electricity rather than producing it, and usually shows up as a small negative number because it uses more power than it returns.

### 4. Year-over-year change
- Always compare a month with **the same month a year earlier** (July 2026 vs. July 2025), never with the month before. Electricity use and solar output are seasonal, so comparing July with June would mostly show the weather.
- Changes in shares are reported in **percentage points**. Changes in amounts and prices are reported in **percent**.

### 5. Coal trend
- Monthly coal generation in GWh, plus a **12-month rolling total** that smooths out seasonal swings so the long-term decline is easy to see.

### 6. Retail electricity price
- Average price in cents per kWh for **residential, commercial, industrial, and all sectors**.
- **Excluded:** "transportation" (Colorado reports one customer) and "other" (reported as zero).
- Prices are in the dollars of each month, **not adjusted for inflation**. The dashboard says so.

## Data quality rules

- The API returns numbers as text. Convert them to numbers, and stop with an error if any value can't be converted.
- A fuel type with no row for a month means "no data," not zero. Store it as missing.
- Small negative values are real (pumped storage and "other" can be net users of power) and are kept.
- **Check on every run:** the five mix categories plus "Other" must add up to the total, and where `REN` is published it must equal `AOR + HYC`, within 0.1 GWh. If either check fails, the run stops before anything is published.

## Spot check (July 2026, from the live API)

These are the reference numbers for testing Phase 3. They are calculated directly from the raw API values.

| Metric | Jul 2025 | Jul 2026 |
|---|---|---|
| Total generation | 5,562.9 GWh | 5,701.9 GWh |
| Renewable share | 39.3% | 45.9% |
| Coal generation | 1,340.7 GWh | 862.9 GWh (−35.6%) |
| Residential price | — | 17.0¢/kWh |

## Out of scope (for now)

- Individual power plants
- Carbon emissions (the EIA has this data, so it's a possible later addition)
- Forecasts
- Inflation-adjusted prices
