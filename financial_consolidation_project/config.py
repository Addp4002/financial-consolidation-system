from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_DIR = APP_DIR / "database"
DB_PATH = DB_DIR / "financial_data.db"

BASE_CURRENCY = "USD"
COUNTRY_CONFIG = {
    "India": {"currency": "INR", "region": "APAC"},
    "USA": {"currency": "USD", "region": "Americas"},
    "Germany": {"currency": "EUR", "region": "EMEA"},
}

# Demonstration-only rates. They are deliberately static so the project runs offline.
# Rate means: 1 unit of the source currency equals this many USD.
DEMO_FX_RATES = {"INR": 0.0120, "USD": 1.0, "EUR": 1.08}

ROLE_LABELS = {
    "Group_CFO": "Group CFO",
    "Regional_Controller": "Regional Controller",
    "Country_Finance_Manager": "Country Finance Manager",
}

DEMO_USERS = [
    {
        "username": "group_cfo",
        "password": "CFO@123",
        "role": "Group_CFO",
        "country": None,
        "region": None,
    },
    {
        "username": "india_manager",
        "password": "India@123",
        "role": "Country_Finance_Manager",
        "country": "India",
        "region": "APAC",
    },
    {
        "username": "us_manager",
        "password": "USA@123",
        "role": "Country_Finance_Manager",
        "country": "USA",
        "region": "Americas",
    },
    {
        "username": "germany_manager",
        "password": "Germany@123",
        "role": "Country_Finance_Manager",
        "country": "Germany",
        "region": "EMEA",
    },
    {
        "username": "americas_controller",
        "password": "Region@123",
        "role": "Regional_Controller",
        "country": None,
        "region": "Americas",
    },
]

FISCAL_YEARS = [2025, 2026, 2027]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
