import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_DIR, DB_PATH, DEMO_FX_RATES


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def get_connection():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    """Create the database schema and load illustrative first-run data."""
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL,
                country TEXT,
                region TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS fx_rates (
                currency TEXT PRIMARY KEY,
                rate_to_usd REAL NOT NULL CHECK(rate_to_usd > 0),
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS financial_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fiscal_year INTEGER NOT NULL,
                quarter TEXT NOT NULL CHECK(quarter IN ('Q1','Q2','Q3','Q4')),
                country TEXT NOT NULL,
                currency TEXT NOT NULL,
                revenue REAL NOT NULL CHECK(revenue >= 0),
                operating_expenses REAL NOT NULL CHECK(operating_expenses >= 0),
                intercompany_revenue REAL NOT NULL DEFAULT 0 CHECK(intercompany_revenue >= 0),
                intercompany_expenses REAL NOT NULL DEFAULT 0 CHECK(intercompany_expenses >= 0),
                updated_by TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(fiscal_year, quarter, country)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                entity TEXT NOT NULL,
                entity_id INTEGER,
                country TEXT,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

        for currency, rate in DEMO_FX_RATES.items():
            conn.execute(
                "INSERT OR IGNORE INTO fx_rates(currency, rate_to_usd, updated_at) VALUES (?, ?, ?)",
                (currency, rate, utc_now()),
            )

        count = conn.execute("SELECT COUNT(*) AS n FROM financial_records").fetchone()["n"]
        if count == 0:
            _seed_financial_records(conn)


def _seed_financial_records(conn: sqlite3.Connection) -> None:
    """Seed synthetic FY2026 records. All values are illustrative, not real company data."""
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    sample = {
        "India": {
            "currency": "INR",
            "revenue": [40_000_000, 42_000_000, 44_000_000, 46_000_000],
            "opex": [26_000_000, 27_000_000, 28_000_000, 29_000_000],
            "ic_revenue": [8_333_333.33, 8_333_333.33, 8_333_333.33, 8_333_333.33],
            "ic_expenses": [4_166_666.67, 4_166_666.67, 4_166_666.67, 4_166_666.67],
        },
        "USA": {
            "currency": "USD",
            "revenue": [1_000_000, 1_050_000, 1_100_000, 1_150_000],
            "opex": [650_000, 680_000, 700_000, 730_000],
            "ic_revenue": [100_000, 100_000, 100_000, 100_000],
            "ic_expenses": [100_000, 100_000, 100_000, 100_000],
        },
        "Germany": {
            "currency": "EUR",
            "revenue": [700_000, 720_000, 740_000, 760_000],
            "opex": [470_000, 480_000, 490_000, 500_000],
            "ic_revenue": [46_296.30, 46_296.30, 46_296.30, 46_296.30],
            "ic_expenses": [92_592.59, 92_592.59, 92_592.59, 92_592.59],
        },
    }
    for country, values in sample.items():
        for index, quarter in enumerate(quarters):
            conn.execute(
                """INSERT INTO financial_records
                (fiscal_year, quarter, country, currency, revenue, operating_expenses,
                 intercompany_revenue, intercompany_expenses, updated_by, updated_at)
                VALUES (2026, ?, ?, ?, ?, ?, ?, ?, 'system_seed', ?)""",
                (
                    quarter,
                    country,
                    values["currency"],
                    values["revenue"][index],
                    values["opex"][index],
                    values["ic_revenue"][index],
                    values["ic_expenses"][index],
                    utc_now(),
                ),
            )
