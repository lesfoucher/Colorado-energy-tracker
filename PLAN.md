# Colorado Energy Tracker — Project Plan

An automated reporting site that tracks how Colorado's electricity is generated (coal, natural gas, wind, solar, hydro) and what it costs, using free public data from the U.S. Energy Information Administration (EIA).

## Why this project

This project is built to match the jobs I'm applying to:

| What the project shows | Roles it supports |
|---|---|
| Writing requirements and defining metrics before building | IT Business Analyst, Consulting Analyst, Business Operations Analyst |
| Pulling, cleaning, and loading data; writing SQL for reporting | Reporting Analyst, Transaction Analytics, HR Analyst |
| Building and publishing a public website | Analyst, Web Development |
| Using an LLM safely, with every number checked before it's published | Software Engineer – AI Applications |
| Running the whole pipeline on a schedule with tests | Jr. DevOps Engineer |

The topic (energy and utilities) is directly relevant to Black & Veatch and Mears, which work on energy and utility infrastructure.

## Questions the tracker answers

1. How is Colorado's electricity generated, and how is that mix changing?
2. What share comes from renewables, and how fast is it growing year over year?
3. How is coal generation declining as plants retire?
4. How are electricity prices changing for homes and businesses?
5. What changed in the latest month, in plain English?

## Data sources

All from the EIA's free API (v2). Requires a free API key from https://www.eia.gov/opendata/.

| Dataset | What it gives | Frequency |
|---|---|---|
| Electric power operational data | Electricity generated in Colorado, by fuel type | Monthly |
| Retail sales | Average electricity price in Colorado, by sector (residential, commercial, industrial) | Monthly |

Both datasets were checked against the live API: monthly data from January 2001 through July 2026. Exact routes, codes, and metric definitions are in [docs/requirements.md](docs/requirements.md).

## Tech stack

- **Python 3.11** for collecting and cleaning the data
- **SQLite** for the database. It's a single file that needs no server, so it works in GitHub Actions. The queries are standard SQL, so they would carry over to PostgreSQL.
- **Plotly.js** in a static web page for the dashboard, hosted on **GitHub Pages**
- **Claude API** for the monthly summaries
- **GitHub Actions** to run everything monthly
- **pytest** for tests

## Phases

### Phase 0 — Setup
- Create the GitHub repo, Python virtual environment, and folder structure
- Store the EIA API key in a `.env` file that is never committed (listed in `.gitignore`)
- **Done when:** a test script can call the EIA API with the key and get a response

### Phase 1 — Requirements document
- Write `docs/requirements.md`: who the tracker is for, the questions above, and exact definitions for every metric (for example, which fuel types count as "renewable")
- **Done when:** every number on the dashboard has a written definition

### Phase 2 — Data pipeline
- Fetch both datasets from the EIA and save the raw responses, so any run can be repeated without calling the API again
- Clean the data: consistent units, dates, and fuel-type names; handle missing months
- Load it into SQLite tables
- Write tests for the cleaning steps
- **Done when:** one command rebuilds the database from scratch, and the tests pass

### Phase 3 — Metrics in SQL
- Write SQL views for each metric: generation mix, renewable share, year-over-year change, coal trend, and price by sector
- Check the results against numbers the EIA publishes in its Colorado state profile
- **Done when:** the metrics match the EIA's own published figures

### Phase 4 — Dashboard
- Export the metrics to JSON and build a static page with:
  - headline numbers for the latest month (renewable share, price, change from last year)
  - a chart of the generation mix over time
  - a price trend chart by sector
  - a data table and a CSV download
- Make it work on phones and in dark mode, then publish it on GitHub Pages
- **Done when:** the live site loads with correct, current data

### Phase 5 — AI monthly summary
- Send the latest month's metrics to Claude and ask for a short plain-English summary
- **Check every number in the summary** against the database. If anything doesn't match, publish no summary that month rather than a wrong one.
- Show the summary on the dashboard, labeled as AI-generated
- **Done when:** the check reliably catches a deliberately wrong number in a test

### Phase 6 — Automation
- A GitHub Actions workflow runs monthly: fetch data → run tests → rebuild metrics → write the summary → redeploy the site
- Store the EIA and Claude API keys as GitHub repository secrets
- **Done when:** the workflow runs on its own and updates the live site

### Phase 7 — Polish
- README with a screenshot, link to the live site, how it works, and how to run it
- Add the project to my resume
- Later, on my Windows PC: build a Power BI dashboard from the same cleaned data

## Folder structure

```
colorado-energy-tracker/
├── PLAN.md
├── README.md
├── .env                  # API keys, never committed
├── docs/
│   └── requirements.md
├── pipeline/
│   ├── fetch.py          # pulls data from the EIA
│   ├── clean.py          # cleans and standardizes it
│   ├── load.py           # loads it into SQLite
│   └── summarize.py      # AI summary and number checking
├── sql/
│   └── metrics.sql       # metric definitions as SQL views
├── data/
│   ├── raw/              # saved API responses
│   └── energy.db         # SQLite database
├── site/                 # the dashboard (published to GitHub Pages)
├── tests/
└── .github/workflows/
    └── monthly.yml
```

## Resume entry (target)

> **Colorado Energy Tracker** | *Python, SQL, Plotly, GitHub Actions, LLM API*
> - Built an automated pipeline that pulls monthly EIA data on Colorado's electricity, cleans it, and loads it into SQL
> - Created a public dashboard tracking renewable share, generation mix, and price trends
> - Added AI-written monthly summaries, with every number automatically checked against the database before publishing

## What I need to do

- [x] Get a free EIA API key: https://www.eia.gov/opendata/
- [ ] Create an empty GitHub repo named `colorado-energy-tracker`
- [ ] Get a Claude API key (needed in Phase 5): https://console.anthropic.com/
