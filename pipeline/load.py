"""Load clean records into SQLite and create the metric views."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "energy.db"
METRICS_SQL = ROOT / "sql" / "metrics.sql"

SCHEMA = """
CREATE TABLE generation (
    period TEXT NOT NULL,      -- 'YYYY-MM'
    fuel   TEXT NOT NULL,      -- EIA fuel code
    gwh    REAL NOT NULL,
    PRIMARY KEY (period, fuel)
);
CREATE TABLE retail (
    period    TEXT NOT NULL,
    sector    TEXT NOT NULL,   -- ALL, RES, COM, IND
    price     REAL,            -- cents per kWh
    sales_gwh REAL,
    customers REAL,
    PRIMARY KEY (period, sector)
);
CREATE TABLE run_log (
    loaded_at TEXT NOT NULL,
    generation_rows INTEGER NOT NULL,
    retail_rows INTEGER NOT NULL
);
"""


def build_database(generation, retail, db_path=DB_PATH):
    """Rebuild the database from scratch. Writes to a temp file first so a failed run never
    leaves a half-built database behind."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)

    con = sqlite3.connect(tmp)
    try:
        con.executescript(SCHEMA)
        con.executemany("INSERT INTO generation VALUES (?, ?, ?)", generation)
        con.executemany("INSERT INTO retail VALUES (?, ?, ?, ?, ?)", retail)
        con.execute("INSERT INTO run_log VALUES (?, ?, ?)",
                    (datetime.now(timezone.utc).isoformat(timespec="seconds"), len(generation), len(retail)))
        con.executescript(METRICS_SQL.read_text())
        con.commit()
    finally:
        con.close()
    tmp.replace(db_path)
    return db_path


def connect(db_path=DB_PATH):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con
