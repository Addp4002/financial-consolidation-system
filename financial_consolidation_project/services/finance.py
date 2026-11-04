from typing import Any

from config import COUNTRY_CONFIG
from database.db import get_connection, utc_now
from services.auth import can_access_country, allowed_countries


AMOUNT_FIELDS = (
    "revenue",
    "operating_expenses",
    "intercompany_revenue",
    "intercompany_expenses",
)


def _validate_amounts(payload: dict[str, Any]) -> dict[str, float]:
    cleaned: dict[str, float] = {}
    for field in AMOUNT_FIELDS:
        try:
            value = float(payload.get(field, 0))
        except (TypeError, ValueError):
            raise ValueError(f"{field.replace('_', ' ').title()} must be a number.")
        if value < 0:
            raise ValueError(f"{field.replace('_', ' ').title()} cannot be negative.")
        cleaned[field] = value

    if cleaned["intercompany_revenue"] > cleaned["revenue"]:
        raise ValueError("Intercompany revenue cannot exceed total revenue.")
    if cleaned["intercompany_expenses"] > cleaned["operating_expenses"]:
        raise ValueError("Intercompany expenses cannot exceed operating expenses.")
    return cleaned


def get_fx_rates() -> dict[str, float]:
    with get_connection() as conn:
        rows = conn.execute("SELECT currency, rate_to_usd FROM fx_rates").fetchall()
    return {row["currency"]: float(row["rate_to_usd"]) for row in rows}


def get_financial_records(user: dict, fiscal_year: int | None = None) -> list[dict]:
    countries = allowed_countries(user)
    if not countries:
        return []
    placeholders = ",".join("?" for _ in countries)
    sql = f"SELECT * FROM financial_records WHERE country IN ({placeholders})"
    params: list[Any] = list(countries)
    if fiscal_year is not None:
        sql += " AND fiscal_year = ?"
        params.append(int(fiscal_year))
    sql += " ORDER BY fiscal_year, quarter, country"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_record_by_id(user: dict, record_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM financial_records WHERE id = ?", (int(record_id),)
        ).fetchone()
    if row is None:
        return None
    record = dict(row)
    if not can_access_country(user, record["country"]):
        return None
    return record


def add_financial_record(user: dict, payload: dict[str, Any]) -> int:
    country = str(payload.get("country", ""))
    if country not in COUNTRY_CONFIG or not can_access_country(user, country):
        raise PermissionError("You do not have permission to add data for this country.")

    year = int(payload.get("fiscal_year", 0))
    quarter = str(payload.get("quarter", ""))
    if year < 2000 or year > 2100:
        raise ValueError("Enter a valid fiscal year.")
    if quarter not in {"Q1", "Q2", "Q3", "Q4"}:
        raise ValueError("Select a valid quarter.")

    values = _validate_amounts(payload)
    currency = COUNTRY_CONFIG[country]["currency"]
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO financial_records
            (fiscal_year, quarter, country, currency, revenue, operating_expenses,
             intercompany_revenue, intercompany_expenses, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                year, quarter, country, currency,
                values["revenue"], values["operating_expenses"],
                values["intercompany_revenue"], values["intercompany_expenses"],
                user["username"], utc_now(),
            ),
        )
        record_id = int(cursor.lastrowid)
        conn.execute(
            """INSERT INTO audit_log
            (username, action, entity, entity_id, country, details, created_at)
            VALUES (?, 'CREATE', 'financial_record', ?, ?, ?, ?)""",
            (user["username"], record_id, country, f"Created {year} {quarter} financial record.", utc_now()),
        )
    return record_id


def update_financial_record(user: dict, record_id: int, payload: dict[str, Any]) -> None:
    record = get_record_by_id(user, record_id)
    if record is None:
        raise PermissionError("Record not found or you do not have permission to edit it.")

    values = _validate_amounts(payload)
    with get_connection() as conn:
        conn.execute(
            """UPDATE financial_records
            SET revenue = ?, operating_expenses = ?, intercompany_revenue = ?,
                intercompany_expenses = ?, updated_by = ?, updated_at = ?
            WHERE id = ?""",
            (
                values["revenue"], values["operating_expenses"],
                values["intercompany_revenue"], values["intercompany_expenses"],
                user["username"], utc_now(), int(record_id),
            ),
        )
        conn.execute(
            """INSERT INTO audit_log
            (username, action, entity, entity_id, country, details, created_at)
            VALUES (?, 'UPDATE', 'financial_record', ?, ?, ?, ?)""",
            (
                user["username"], int(record_id), record["country"],
                f"Updated {record['fiscal_year']} {record['quarter']} financial amounts.", utc_now(),
            ),
        )



def import_financial_records(user: dict, rows: list[dict[str, Any]]) -> int:
    """Import a CSV batch atomically after validating every row and its access scope."""
    if not rows:
        raise ValueError("The uploaded CSV contains no data rows.")

    validated = []
    for index, row in enumerate(rows, start=2):
        country = str(row.get("country", "")).strip()
        if country not in COUNTRY_CONFIG or not can_access_country(user, country):
            raise PermissionError(f"CSV row {index}: you do not have permission to import data for '{country}'.")
        try:
            year = int(row.get("fiscal_year"))
        except (TypeError, ValueError):
            raise ValueError(f"CSV row {index}: fiscal_year must be a whole number.")
        quarter = str(row.get("quarter", "")).strip().upper()
        if year < 2000 or year > 2100 or quarter not in {"Q1", "Q2", "Q3", "Q4"}:
            raise ValueError(f"CSV row {index}: enter a valid fiscal_year and quarter (Q1-Q4).")
        values = _validate_amounts(row)
        validated.append((
            year, quarter, country, COUNTRY_CONFIG[country]["currency"],
            values["revenue"], values["operating_expenses"],
            values["intercompany_revenue"], values["intercompany_expenses"],
        ))

    with get_connection() as conn:
        for row in validated:
            cursor = conn.execute(
                """INSERT INTO financial_records
                (fiscal_year, quarter, country, currency, revenue, operating_expenses,
                 intercompany_revenue, intercompany_expenses, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*row, user["username"], utc_now()),
            )
            conn.execute(
                """INSERT INTO audit_log
                (username, action, entity, entity_id, country, details, created_at)
                VALUES (?, 'IMPORT', 'financial_record', ?, ?, ?, ?)""",
                (user["username"], int(cursor.lastrowid), row[2],
                 f"Imported FY{row[0]} {row[1]} financial record from CSV.", utc_now()),
            )
    return len(validated)

def get_audit_logs(user: dict, limit: int = 200) -> list[dict]:
    if user.get("role") == "Group_CFO":
        sql = "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?"
        params: tuple = (int(limit),)
    else:
        countries = allowed_countries(user)
        if not countries:
            return []
        placeholders = ",".join("?" for _ in countries)
        sql = f"SELECT * FROM audit_log WHERE country IN ({placeholders}) ORDER BY id DESC LIMIT ?"
        params = tuple(countries) + (int(limit),)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]
