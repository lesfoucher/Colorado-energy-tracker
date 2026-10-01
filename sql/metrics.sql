-- Metric definitions for the Colorado Energy Tracker.
-- Each view matches a definition in docs/requirements.md.

-- One row per month, one column per fuel (GWh). Missing fuels stay NULL here.
CREATE VIEW v_generation_monthly AS
SELECT
    period,
    MAX(CASE WHEN fuel = 'ALL' THEN gwh END) AS total_gwh,
    MAX(CASE WHEN fuel = 'COW' THEN gwh END) AS coal_gwh,
    MAX(CASE WHEN fuel = 'NG'  THEN gwh END) AS gas_gwh,
    MAX(CASE WHEN fuel = 'WND' THEN gwh END) AS wind_gwh,
    MAX(CASE WHEN fuel = 'SUN' THEN gwh END) AS solar_gwh,
    MAX(CASE WHEN fuel = 'HYC' THEN gwh END) AS hydro_gwh,
    MAX(CASE WHEN fuel = 'AOR' THEN gwh END) AS aor_gwh,
    MAX(CASE WHEN fuel = 'REN' THEN gwh END) AS ren_gwh,
    MAX(CASE WHEN fuel = 'DPV' THEN gwh END) AS rooftop_solar_gwh  -- EIA estimate, from 2014; not in the total
FROM generation
GROUP BY period;

-- Metrics 1-3: total generation, generation mix, renewable share.
-- A source with no data in a month contributes 0 to the mix (for example, no solar plants in 2001).
-- "Other" is the remainder, so the mix always adds up to the total.
-- Renewable = AOR + HYC, because REN is missing for 2001-2002 (see requirements).
CREATE VIEW v_mix AS
SELECT
    period,
    total_gwh,
    COALESCE(coal_gwh, 0)  AS coal_gwh,
    COALESCE(gas_gwh, 0)   AS gas_gwh,
    COALESCE(wind_gwh, 0)  AS wind_gwh,
    COALESCE(solar_gwh, 0) AS solar_gwh,
    COALESCE(hydro_gwh, 0) AS hydro_gwh,
    total_gwh - COALESCE(coal_gwh, 0) - COALESCE(gas_gwh, 0) - COALESCE(wind_gwh, 0)
              - COALESCE(solar_gwh, 0) - COALESCE(hydro_gwh, 0) AS other_gwh,
    COALESCE(aor_gwh, 0) + COALESCE(hydro_gwh, 0) AS renewable_gwh,
    100.0 * (COALESCE(aor_gwh, 0) + COALESCE(hydro_gwh, 0)) / total_gwh AS renewable_share_pct,
    100.0 * COALESCE(coal_gwh, 0) / total_gwh AS coal_share_pct,
    rooftop_solar_gwh
FROM v_generation_monthly;

-- Metric 4: year-over-year change, always against the same month a year earlier.
-- Shares change in percentage points (pp); amounts change in percent.
CREATE VIEW v_mix_yoy AS
SELECT
    cur.period,
    cur.total_gwh,
    cur.renewable_share_pct,
    cur.coal_gwh,
    prev.period AS prior_period,
    cur.renewable_share_pct - prev.renewable_share_pct AS renewable_share_change_pp,
    100.0 * (cur.total_gwh - prev.total_gwh) / prev.total_gwh AS total_change_pct,
    100.0 * (cur.renewable_gwh - prev.renewable_gwh) / NULLIF(prev.renewable_gwh, 0) AS renewable_change_pct,
    100.0 * (cur.coal_gwh - prev.coal_gwh) / NULLIF(prev.coal_gwh, 0) AS coal_change_pct
FROM v_mix AS cur
JOIN v_mix AS prev
  ON prev.period = printf('%04d', CAST(substr(cur.period, 1, 4) AS INTEGER) - 1) || substr(cur.period, 5);

-- Metric 5: coal trend, with a 12-month rolling total.
-- The rolling total is NULL until 12 months of data exist.
CREATE VIEW v_coal_trend AS
SELECT
    period,
    coal_gwh,
    CASE WHEN COUNT(*) OVER w = 12 THEN SUM(coal_gwh) OVER w END AS coal_rolling_12m_gwh
FROM v_mix
WINDOW w AS (ORDER BY period ROWS BETWEEN 11 PRECEDING AND CURRENT ROW);

-- Annual totals by source, for complete calendar years only.
CREATE VIEW v_annual_mix AS
SELECT
    substr(period, 1, 4) AS year,
    SUM(total_gwh) AS total_gwh,
    SUM(coal_gwh)  AS coal_gwh,
    SUM(gas_gwh)   AS gas_gwh,
    SUM(wind_gwh)  AS wind_gwh,
    SUM(solar_gwh) AS solar_gwh,
    SUM(hydro_gwh) AS hydro_gwh,
    SUM(other_gwh) AS other_gwh,
    100.0 * SUM(renewable_gwh) / SUM(total_gwh) AS renewable_share_pct
FROM v_mix
GROUP BY substr(period, 1, 4)
HAVING COUNT(*) = 12;

-- Metric 6: retail price by sector (cents per kWh, not adjusted for inflation), with year-over-year change.
CREATE VIEW v_price AS
SELECT
    cur.period,
    cur.sector,
    cur.price AS price_cents_kwh,
    100.0 * (cur.price - prev.price) / NULLIF(prev.price, 0) AS price_change_pct
FROM retail AS cur
LEFT JOIN retail AS prev
  ON prev.sector = cur.sector
 AND prev.period = printf('%04d', CAST(substr(cur.period, 1, 4) AS INTEGER) - 1) || substr(cur.period, 5);
