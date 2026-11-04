# Group Finance: Planning, Consolidation & Analytics

A runnable portfolio project that simulates selected workflows commonly associated with SAP BPC, SAP Analytics Cloud (SAC) Planning, and SAP S/4HANA Group Reporting.

**Important:** This is an educational simulation built with Python, Streamlit and SQLite. It is not SAP software, it does not connect to an SAP system, and the sample financial figures and FX rates are fictional.

## What the application does

- Authenticates demo users with salted PBKDF2 password hashes.
- Applies server-side role and country/region access checks.
- Stores quarterly entity-level financial data in SQLite.
- Supports creating and updating financial records, plus all-or-nothing CSV batch imports.
- Writes create, update and CSV-import events to an audit log.
- Translates INR, USD and EUR values into a common USD reporting currency using static demo FX rates.
- Produces a group consolidation matrix and applies intercompany revenue/expense eliminations.
- Provides KPI cards, country charts and quarterly trends.
- Provides interactive revenue-growth and expense-inflation assumptions for a what-if forecast.
- Exports visible entity data and the consolidated matrix as CSV.

## Technology

| Layer | Technology |
|---|---|
| User interface | Streamlit |
| Business logic | Python |
| Database | SQLite |
| Data processing | Pandas |
| Charts | Plotly |
| Authentication | PBKDF2-HMAC-SHA256 password hashing |

## 1. Install Python

Use Python 3.10 or later. During installation on Windows, select **Add Python to PATH**.

Check the installation:

```bash
python --version
```

## 2. Open the project folder

Extract the ZIP file, open a terminal, and move into the project folder:

```bash
cd financial_consolidation_project
```

## 3. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 4. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Run the application

```bash
streamlit run app.py
```

Streamlit will print a local address, normally `http://localhost:8501`. Open it in your browser. The SQLite database and demo users are created automatically on the first launch.

## Demo login accounts

| Role | Username | Password | Access |
|---|---|---|---|
| Group CFO | `group_cfo` | `CFO@123` | India, USA and Germany; full group consolidation |
| India Finance Manager | `india_manager` | `India@123` | India only |
| US Finance Manager | `us_manager` | `USA@123` | USA only |
| Germany Finance Manager | `germany_manager` | `Germany@123` | Germany only |
| Americas Controller | `americas_controller` | `Region@123` | Assigned Americas region (USA in this demo) |

These credentials are only for a local demonstration. Do not expose this demo application publicly with the sample credentials.

## Suggested walkthrough

1. Sign in as `india_manager`. Open **Financial Data** and notice that only India records are available.
2. Sign out and sign in as `us_manager`. Update one of the USA quarterly records. The save operation is recorded in the audit log.
   You can also use the CSV import panel with `data/financial_records_template.csv` as the column template. Import batches are validated against the signed-in user's scope and duplicate country/year/quarter combinations cancel the batch.
3. Sign out and sign in as `group_cfo`. Open **Financial Consolidation** to see the complete India/USA/Germany matrix.
4. Review the intercompany reconciliation. The starter records are designed to balance after conversion to USD, subject to minor rounding from the sample FX rates.
5. Open **Planning & Forecasting**. Move the **Projected Growth Rate %** slider and watch the forecast KPIs and chart recalculate.
6. Open **Audit Trail** to inspect changes made by users.

## Application structure

```text
financial_consolidation_project/
├── app.py                         # Streamlit interface and navigation
├── config.py                      # Countries, roles, currencies and demo users
├── requirements.txt               # Python dependencies
├── database/
│   ├── __init__.py
│   └── db.py                       # SQLite schema, connection and sample data
├── services/
│   ├── __init__.py
│   ├── auth.py                     # Authentication and access-control rules
│   ├── finance.py                  # Financial record CRUD and audit logging
│   ├── consolidation.py            # Currency conversion and eliminations
│   └── forecast.py                 # What-if planning calculations
├── tests/
│   └── test_services.py            # Basic access and calculation tests
└── data/
    └── README.txt                  # Notes about demo data
```

## 2-minute explanation of the business logic

### Role-based security

The UI filters countries based on the logged-in user's role, but the important check is also performed inside the service layer before a record is read or changed. A Country Finance Manager can only access the assigned country. A Regional Controller can access entities assigned to the controller's region. The Group CFO can access all entities and the full consolidation matrix.

### Currency translation

Each country has a local currency. The project multiplies local values by the configured USD exchange rate:

`USD amount = local-currency amount × USD exchange rate`

The sample rates are fixed in `config.py` so that the application can run without an internet connection. They are not live market rates.

### Intercompany eliminations

The consolidation routine first translates each entity's balances into USD. It then removes intercompany revenue from group revenue and intercompany expenses from group operating expenses:

`Consolidated revenue = Gross revenue − Intercompany revenue`

`Consolidated operating expenses = Gross operating expenses − Intercompany expenses`

The reconciliation page compares the two elimination totals. In an actual group close, the finance team would also match trading partner / partner-unit information and investigate mismatches.

### Planning calculation

The planning screen uses two assumptions:

`Projected revenue = Actual revenue × (1 + growth rate)`

`Projected expenses = Actual operating expenses × (1 + expense inflation rate)`

`Projected net profit = Projected revenue − Projected expenses`

Streamlit reruns the calculation when a slider value changes, so the user sees an immediate scenario update. This is an interactive what-if simulation; it does not save an approved budget version.

## Run the tests

From the project root, with the virtual environment activated:

```bash
python -m unittest discover -s tests -v
```

## Reset the local demo database

Stop Streamlit, then delete `database/financial_data.db`. Start the app again. The schema, demo users and sample FY2026 records will be recreated automatically.

## Important production gaps

This project is intentionally a learning prototype. Before production use, it would need HTTPS, secret management, password reset and account administration, stronger session controls, database migrations, automated backups, comprehensive tests, approval workflows, data-version management, configurable FX translation rules, intercompany partner matching, and security review. The default SQLite file is suitable for a local demo, not concurrent enterprise workloads.

## Mapping to SAP concepts

| Project feature | Related SAP concept being simulated |
|---|---|
| Entity-level actual data and validation | SAP BPC data input / planning model concepts |
| Scenario sliders and forecast calculation | SAP Analytics Cloud Planning concepts |
| KPI cards and interactive charts | SAP Analytics Cloud stories / dashboards |
| Currency translation and intercompany eliminations | S/4HANA Group Reporting concepts |
| User roles and scoped access | SAP authorization / data access concepts |

The implementation is not a one-to-one reproduction of SAP configuration or processing. Use it to demonstrate that you understand the business flow and can build a small working prototype.
