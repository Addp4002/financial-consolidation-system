import hashlib
import hmac
import os

from config import DEMO_USERS
from database.db import get_connection, utc_now


def _hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 180_000)
    return password_hash.hex(), salt.hex()


def seed_demo_users() -> None:
    with get_connection() as conn:
        for user in DEMO_USERS:
            exists = conn.execute(
                "SELECT id FROM users WHERE username = ?", (user["username"],)
            ).fetchone()
            if exists:
                continue
            password_hash, salt = _hash_password(user["password"])
            conn.execute(
                """INSERT INTO users
                (username, password_hash, salt, role, country, region, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    user["username"],
                    password_hash,
                    salt,
                    user["role"],
                    user["country"],
                    user["region"],
                    utc_now(),
                ),
            )


def authenticate(username: str, password: str) -> dict | None:
    username = username.strip()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? AND active = 1", (username,)
        ).fetchone()
    if row is None:
        return None

    candidate_hash, _ = _hash_password(password, row["salt"])
    if not hmac.compare_digest(candidate_hash, row["password_hash"]):
        return None

    return {
        "id": row["id"],
        "username": row["username"],
        "role": row["role"],
        "country": row["country"],
        "region": row["region"],
    }


def can_access_country(user: dict, country: str) -> bool:
    role = user.get("role")
    if role == "Group_CFO":
        return True
    if role == "Country_Finance_Manager":
        return user.get("country") == country
    if role == "Regional_Controller":
        from config import COUNTRY_CONFIG
        return COUNTRY_CONFIG.get(country, {}).get("region") == user.get("region")
    return False


def allowed_countries(user: dict) -> list[str]:
    from config import COUNTRY_CONFIG
    return [country for country in COUNTRY_CONFIG if can_access_country(user, country)]


def can_view_group_consolidation(user: dict) -> bool:
    return user.get("role") == "Group_CFO"
