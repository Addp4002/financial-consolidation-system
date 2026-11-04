from __future__ import annotations

import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st

from config import BASE_CURRENCY, COUNTRY_CONFIG, FISCAL_YEARS, QUARTERS, ROLE_LABELS
from database.db import initialize_database
from services.auth import authenticate, can_view_group_consolidation, allowed_countries, seed_demo_users
from services.consolidation import consolidate_records, convert_amount
from services.finance import (
    add_financial_record,
    get_audit_logs,
    get_financial_records,
    import_financial_records,
    get_fx_rates,
    get_record_by_id,
    update_financial_record,
)
from services.forecast import build_forecast


st.set_page_config(
    page_title="Group Finance | Planning & Consolidation",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_database()
seed_demo_users()


# ---------- Shared helpers ----------
def money(value: float, currency: str = BASE_CURRENCY) -> str:
    symbol = {"USD": "$", "INR": "₹", "EUR": "€"}.get(currency, currency + " ")
    return f"{symbol}{float(value):,.0f}"


def money_usd(value: float) -> str:
    return money(value, "USD")


def records_frame(records: list[dict], fx_rates: dict[str, float]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["revenue_usd"] = df.apply(
        lambda r: convert_amount(r["revenue"], r["currency"], fx_rates), axis=1
    )
    df["opex_usd"] = df.apply(
        lambda r: convert_amount(r["operating_expenses"], r["currency"], fx_rates), axis=1
    )
    df["ic_revenue_usd"] = df.apply(
        lambda r: convert_amount(r["intercompany_revenue"], r["currency"], fx_rates), axis=1
    )
    df["ic_expenses_usd"] = df.apply(
        lambda r: convert_amount(r["intercompany_expenses"], r["currency"], fx_rates), axis=1
    )
    df["consolidated_revenue_usd"] = df["revenue_usd"] - df["ic_revenue_usd"]
    df["consolidated_opex_usd"] = df["opex_usd"] - df["ic_expenses_usd"]
    df["net_profit_usd"] = df["consolidated_revenue_usd"] - df["consolidated_opex_usd"]
    return df


def get_year_records(user: dict, fiscal_year: int):
    return get_financial_records(user, fiscal_year)


def metric_row(revenue: float, expenses: float, profit: float, margin: float):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Revenue", money_usd(revenue))
    c2.metric("Operating Expenses", money_usd(expenses))
    c3.metric("Net Profit", money_usd(profit))
    c4.metric("Net Profit Margin", f"{margin:.1f}%")


def page_header(title: str, subtitle: str):
    st.title(title)
    st.caption(subtitle)
    st.divider()


def login_page():
    st.markdown(
        """
        <div style='max-width:760px;margin:2rem auto 1rem auto;'>
            <div style='font-size:0.85rem;letter-spacing:0.12em;color:#6b7280;'>GROUP FINANCE PLATFORM</div>
            <h1 style='margin:0.2rem 0 0.3rem 0;'>Planning, Consolidation & Analytics</h1>
            <p style='color:#6b7280;font-size:1.05rem;'>A learning project that simulates core SAP BPC, SAC Planning and S/4HANA Group Reporting workflows.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, center, right = st.columns([1, 1.15, 1])
    with center:
        with st.container(border=True):
            st.subheader("Sign in")
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                submitted = st.form_submit_button("Log in", use_container_width=True, type="primary")
            if submitted:
                user = authenticate(username, password)
                if user:
                    st.session_state["user"] = user
                    st.rerun()
                else:
                    st.error("The username or password is incorrect, or the account is inactive.")
            with st.expander("Demo accounts for local testing"):
                st.markdown(
                    """
                    | Role | Username | Password |
                    |---|---|---|
                    | Group CFO | `group_cfo` | `CFO@123` |
                    | India Finance Manager | `india_manager` | `India@123` |
                    | US Finance Manager | `us_manager` | `USA@123` |
                    | Germany Finance Manager | `germany_manager` | `Germany@123` |
                    | Americas Controller | `americas_controller` | `Region@123` |
                    """
                )
                st.warning("These are sample credentials for a local portfolio project. Change them before any real deployment.")
    st.markdown(
        "<div style='text-align:center;color:#9ca3af;margin-top:2rem;font-size:0.8rem;'>Demo data only · USD is the reporting currency · No connection to a live SAP system</div>",
        unsafe_allow_html=True,
    )


# ---------- Pages ----------
def dashboard_page(user: dict, fiscal_year: int, records: list[dict], fx_rates: dict[str, float]):
    page_header("Executive Dashboard", "Financial performance at a glance, with figures scoped to your access rights.")
    if not records:
        st.info("No financial records are available for this fiscal year and your assigned data scope.")
        return

    result = consolidate_records(records, fx_rates)
    scope_label = "Group consolidated view" if user["role"] == "Group_CFO" else (
        f"{user['region']} regional view" if user["role"] == "Regional_Controller" else f"{user['country']} entity view"
    )
    st.caption(f"{scope_label} · FY{fiscal_year} · Reporting currency: USD")
    metric_row(
        result["consolidated_revenue_usd"],
        result["consolidated_opex_usd"],
        result["net_profit_usd"],
        result["net_profit_margin_pct"],
    )

    df = records_frame(records, fx_rates)
    col1, col2 = st.columns([1.1, 1])
    with col1:
        st.subheader("Revenue by country")
        country_df = df.groupby("country", as_index=False).agg(
            Revenue=("consolidated_revenue_usd", "sum"),
            Expenses=("consolidated_opex_usd", "sum"),
        )
        fig = px.bar(
            country_df.melt(id_vars="country", var_name="Metric", value_name="USD"),
            x="country", y="USD", color="Metric", barmode="group",
            labels={"country": "Country", "USD": "USD", "Metric": "Financial metric"},
        )
        fig.update_layout(legend_title_text="", margin=dict(l=10, r=10, t=25, b=10), height=340)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.subheader("Profit contribution")
        profit_df = df.groupby("country", as_index=False)["net_profit_usd"].sum()
        fig = px.pie(profit_df, names="country", values="net_profit_usd", hole=0.55)
        fig.update_layout(margin=dict(l=10, r=10, t=25, b=10), height=340, legend_title_text="Country")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Quarterly financial trend")
    quarter_df = df.groupby("quarter", as_index=False).agg(
        Revenue=("consolidated_revenue_usd", "sum"),
        Expenses=("consolidated_opex_usd", "sum"),
        Profit=("net_profit_usd", "sum"),
    )
    quarter_df["quarter"] = pd.Categorical(quarter_df["quarter"], categories=QUARTERS, ordered=True)
    quarter_df = quarter_df.sort_values("quarter")
    trend = quarter_df.melt(id_vars="quarter", var_name="Metric", value_name="USD")
    fig = px.line(trend, x="quarter", y="USD", color="Metric", markers=True)
    fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), height=330, legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

    st.caption("All amounts are illustrative. Country values are converted using the static demo FX rates configured in this project.")


def financial_data_page(user: dict, fiscal_year: int, fx_rates: dict[str, float]):
    page_header("Financial Data Management", "Maintain entity-level actuals. Your role controls which countries you can see and edit.")
    records = get_year_records(user, fiscal_year)
    allowed = allowed_countries(user)

    st.subheader(f"Financial records · FY{fiscal_year}")
    if records:
        df = pd.DataFrame(records)
        display_columns = [
            "id", "fiscal_year", "quarter", "country", "currency", "revenue",
            "operating_expenses", "intercompany_revenue", "intercompany_expenses",
            "updated_by", "updated_at",
        ]
        st.dataframe(df[display_columns], use_container_width=True, hide_index=True)
        csv = df[display_columns].to_csv(index=False).encode("utf-8")
        st.download_button("Download visible records as CSV", csv, f"financial_records_FY{fiscal_year}.csv", "text/csv")
    else:
        st.info("There are no records in your scope for this year yet. You can create the first record below.")

    with st.expander("Import multiple records from CSV"):
        st.write("Required columns: `country`, `fiscal_year`, `quarter`, `revenue`, `operating_expenses`, `intercompany_revenue`, `intercompany_expenses`.")
        uploaded_csv = st.file_uploader("Choose a CSV file", type=["csv"], key="financial_csv_upload")
        if uploaded_csv is not None:
            try:
                uploaded_csv.seek(0)
                upload_df = pd.read_csv(uploaded_csv)
                required_columns = {
                    "country", "fiscal_year", "quarter", "revenue", "operating_expenses",
                    "intercompany_revenue", "intercompany_expenses",
                }
                missing_columns = required_columns - set(upload_df.columns)
                if missing_columns:
                    st.error("Missing required columns: " + ", ".join(sorted(missing_columns)))
                else:
                    st.dataframe(upload_df.head(10), use_container_width=True, hide_index=True)
                    if st.button("Validate and import CSV", type="primary", key="import_financial_csv"):
                        try:
                            imported_count = import_financial_records(user, upload_df.to_dict("records"))
                            st.success(f"Successfully imported {imported_count} records. The import is recorded in the audit log.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Import cancelled: at least one country/year/quarter combination already exists. No rows from this batch were saved.")
                        except (ValueError, PermissionError) as exc:
                            st.error(str(exc))
            except Exception as exc:
                st.error(f"Could not read the CSV file: {exc}")

    st.divider()
    add_col, edit_col = st.columns(2)
    with add_col:
        with st.container(border=True):
            st.subheader("Add financial record")
            with st.form("add_record_form"):
                country = st.selectbox("Country", allowed, key="add_country")
                year = st.number_input("Fiscal year", min_value=2000, max_value=2100, value=fiscal_year, step=1, key="add_year")
                quarter = st.selectbox("Quarter", QUARTERS, key="add_quarter")
                currency = COUNTRY_CONFIG[country]["currency"]
                st.caption(f"Currency is assigned automatically: {currency}")
                revenue = st.number_input(f"Revenue ({currency})", min_value=0.0, value=0.0, step=1000.0, key="add_revenue")
                opex = st.number_input(f"Operating expenses ({currency})", min_value=0.0, value=0.0, step=1000.0, key="add_opex")
                ic_rev = st.number_input(f"Intercompany revenue ({currency})", min_value=0.0, value=0.0, step=1000.0, key="add_ic_rev")
                ic_opex = st.number_input(f"Intercompany expenses ({currency})", min_value=0.0, value=0.0, step=1000.0, key="add_ic_opex")
                add_clicked = st.form_submit_button("Save new record", type="primary", use_container_width=True)
            if add_clicked:
                try:
                    record_id = add_financial_record(user, {
                        "country": country, "fiscal_year": year, "quarter": quarter,
                        "revenue": revenue, "operating_expenses": opex,
                        "intercompany_revenue": ic_rev, "intercompany_expenses": ic_opex,
                    })
                    st.success(f"Record #{record_id} saved.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("A record already exists for this country, fiscal year and quarter. Edit the existing record instead.")
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))

    with edit_col:
        with st.container(border=True):
            st.subheader("Edit existing record")
            if records:
                options = {
                    f"#{r['id']} · {r['country']} · FY{r['fiscal_year']} {r['quarter']}": r["id"]
                    for r in records
                }
                selected_label = st.selectbox("Select a record", list(options.keys()), key="edit_record_select")
                selected = get_record_by_id(user, options[selected_label])
                if selected:
                    currency = selected["currency"]
                    with st.form("edit_record_form"):
                        st.caption(f"{selected['country']} · FY{selected['fiscal_year']} {selected['quarter']} · {currency}")
                        e_revenue = st.number_input("Revenue", min_value=0.0, value=float(selected["revenue"]), step=1000.0)
                        e_opex = st.number_input("Operating expenses", min_value=0.0, value=float(selected["operating_expenses"]), step=1000.0)
                        e_ic_rev = st.number_input("Intercompany revenue", min_value=0.0, value=float(selected["intercompany_revenue"]), step=1000.0)
                        e_ic_opex = st.number_input("Intercompany expenses", min_value=0.0, value=float(selected["intercompany_expenses"]), step=1000.0)
                        save_clicked = st.form_submit_button("Update record", type="primary", use_container_width=True)
                    if save_clicked:
                        try:
                            update_financial_record(user, selected["id"], {
                                "revenue": e_revenue, "operating_expenses": e_opex,
                                "intercompany_revenue": e_ic_rev, "intercompany_expenses": e_ic_opex,
                            })
                            st.success("Financial record updated. The change has been written to the audit log.")
                            st.rerun()
                        except (ValueError, PermissionError) as exc:
                            st.error(str(exc))
            else:
                st.caption("Create a record to enable editing.")

    st.info("Access is checked again in the database service when a record is saved. Hiding a country in the screen is not the only security control.")


def consolidation_page(user: dict, fiscal_year: int, fx_rates: dict[str, float]):
    page_header("Group Financial Consolidation", "A simulated group close: currency translation, aggregation and intercompany eliminations.")
    if not can_view_group_consolidation(user):
        st.error("Only the Group CFO role can access the full group consolidated matrix.")
        return

    records = get_year_records(user, fiscal_year)
    if not records:
        st.info("No financial data is available for the selected fiscal year.")
        return

    result = consolidate_records(records, fx_rates)
    st.caption(f"Full group view · FY{fiscal_year} · Reporting currency: USD")
    metric_row(
        result["consolidated_revenue_usd"], result["consolidated_opex_usd"],
        result["net_profit_usd"], result["net_profit_margin_pct"],
    )

    matrix_rows = []
    for item in result["countries"]:
        matrix_rows.append({
            "Country": item["country"],
            "Local currency": item["currency"],
            "Revenue (USD)": item["revenue_usd"],
            "IC revenue elimination (USD)": item["ic_revenue_usd"],
            "Consolidated revenue (USD)": item["revenue_usd"] - item["ic_revenue_usd"],
            "Operating expenses (USD)": item["operating_expenses_usd"],
            "IC expense elimination (USD)": item["ic_expenses_usd"],
            "Consolidated expenses (USD)": item["operating_expenses_usd"] - item["ic_expenses_usd"],
            "Net profit (USD)": item["net_profit_usd"],
        })
    matrix = pd.DataFrame(matrix_rows)
    total_row = {
        "Country": "GROUP TOTAL",
        "Local currency": "USD",
        "Revenue (USD)": result["gross_revenue_usd"],
        "IC revenue elimination (USD)": result["ic_revenue_elimination_usd"],
        "Consolidated revenue (USD)": result["consolidated_revenue_usd"],
        "Operating expenses (USD)": result["gross_opex_usd"],
        "IC expense elimination (USD)": result["ic_expense_elimination_usd"],
        "Consolidated expenses (USD)": result["consolidated_opex_usd"],
        "Net profit (USD)": result["net_profit_usd"],
    }
    matrix = pd.concat([matrix, pd.DataFrame([total_row])], ignore_index=True)
    st.subheader("Consolidated matrix")
    st.dataframe(
        matrix.style.format({column: "${:,.0f}" for column in matrix.columns if "USD" in column}),
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download consolidated matrix as CSV",
        matrix.to_csv(index=False).encode("utf-8"),
        f"group_consolidation_FY{fiscal_year}.csv",
        "text/csv",
    )

    st.subheader("Intercompany reconciliation")
    r1, r2, r3 = st.columns(3)
    r1.metric("IC revenue to eliminate", money_usd(result["ic_revenue_elimination_usd"]))
    r2.metric("IC expenses to eliminate", money_usd(result["ic_expense_elimination_usd"]))
    difference = result["ic_reconciliation_difference_usd"]
    r3.metric("Difference", money_usd(difference), delta="Balanced" if abs(difference) < 1 else "Needs review")
    if abs(difference) < 1:
        st.success("Intercompany revenue and expense eliminations reconcile within the $1 tolerance.")
    else:
        st.warning("Intercompany eliminations do not balance. Review entity submissions before treating this as a final group close.")

    st.caption("This learning model performs simple aggregation and elimination. Real SAP Group Reporting includes additional controls such as partner-unit matching, FS item mapping, validation rules, currency translation methods and closing tasks.")


def planning_page(user: dict, fiscal_year: int, records: list[dict], fx_rates: dict[str, float]):
    page_header("Planning & Forecasting", "Explore a what-if budget scenario. The forecast recalculates immediately when a planning assumption changes.")
    if not records:
        st.info("No actual data is available for the selected fiscal year and your access scope.")
        return

    actual = consolidate_records(records, fx_rates)
    actual_revenue = actual["consolidated_revenue_usd"]
    actual_expenses = actual["consolidated_opex_usd"]
    actual_profit = actual["net_profit_usd"]

    st.subheader("Planning assumptions")
    left, right = st.columns(2)
    with left:
        growth = st.slider("Projected Growth Rate %", min_value=-10, max_value=40, value=10, step=1)
    with right:
        expense_inflation = st.slider("Operating Expense Inflation %", min_value=-10, max_value=30, value=5, step=1)

    forecast = build_forecast(actual_revenue, actual_expenses, growth, expense_inflation)
    st.divider()
    st.subheader("Forecast output")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Projected Revenue", money_usd(forecast["projected_revenue"]), f"{growth:+.0f}%")
    p2.metric("Projected Expenses", money_usd(forecast["projected_expenses"]), f"{expense_inflation:+.0f}%")
    p3.metric("Projected Net Profit", money_usd(forecast["projected_profit"]), money_usd(forecast["projected_profit"] - actual_profit))
    p4.metric("Projected Net Profit Margin", f"{forecast['projected_margin_pct']:.1f}%", f"{forecast['projected_margin_pct'] - actual['net_profit_margin_pct']:+.1f} pp")

    comparison = pd.DataFrame([
        {"Metric": "Revenue", "Actual": actual_revenue, "Scenario forecast": forecast["projected_revenue"]},
        {"Metric": "Operating expenses", "Actual": actual_expenses, "Scenario forecast": forecast["projected_expenses"]},
        {"Metric": "Net profit", "Actual": actual_profit, "Scenario forecast": forecast["projected_profit"]},
    ])
    chart_df = comparison.melt(id_vars="Metric", var_name="Version", value_name="USD")
    fig = px.bar(chart_df, x="Metric", y="USD", color="Version", barmode="group", text_auto=".2s")
    fig.update_layout(margin=dict(l=10, r=10, t=25, b=10), height=390, legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Country-level forecast allocation")
    country_rows = []
    for item in actual["countries"]:
        country_rows.append({
            "Country": item["country"],
            "Actual revenue (USD)": item["revenue_usd"] - item["ic_revenue_usd"],
            "Forecast revenue (USD)": (item["revenue_usd"] - item["ic_revenue_usd"]) * (1 + growth / 100),
            "Actual expenses (USD)": item["operating_expenses_usd"] - item["ic_expenses_usd"],
            "Forecast expenses (USD)": (item["operating_expenses_usd"] - item["ic_expenses_usd"]) * (1 + expense_inflation / 100),
        })
    st.dataframe(pd.DataFrame(country_rows).style.format({c: "${:,.0f}" for c in country_rows[0] if "USD" in c}), use_container_width=True, hide_index=True)
    st.caption("This is a scenario calculation, not a saved budget version. A production planning workflow would add versioning, approval status and write-back controls.")


def audit_page(user: dict):
    page_header("Audit Trail", "Review changes made to financial records within your permitted data scope.")
    logs = get_audit_logs(user)
    if not logs:
        st.info("No audit events are available in your access scope yet.")
        return
    df = pd.DataFrame(logs)
    df = df.rename(columns={
        "username": "User", "action": "Action", "entity": "Object",
        "entity_id": "Record ID", "country": "Country", "details": "Details",
        "created_at": "Timestamp",
    })
    st.dataframe(df[["Timestamp", "User", "Action", "Object", "Record ID", "Country", "Details"]], use_container_width=True, hide_index=True)


# ---------- Main application ----------
if "user" not in st.session_state:
    login_page()
    st.stop()

user = st.session_state["user"]
fx_rates = get_fx_rates()

with st.sidebar:
    st.markdown("## 📊 Group Finance")
    st.caption("Planning · Consolidation · Analytics")
    st.divider()
    st.write(f"**{user['username']}**")
    st.caption(ROLE_LABELS.get(user["role"], user["role"]))
    if user.get("country"):
        st.caption(f"Entity: {user['country']}")
    elif user.get("region"):
        st.caption(f"Region: {user['region']}")
    else:
        st.caption("Scope: All entities")
    st.divider()

    pages = ["Executive Dashboard", "Financial Data", "Planning & Forecasting", "Audit Trail"]
    if can_view_group_consolidation(user):
        pages.insert(2, "Financial Consolidation")
    selected_page = st.radio("Navigate", pages, label_visibility="collapsed")
    selected_year = st.selectbox("Fiscal year", FISCAL_YEARS, index=FISCAL_YEARS.index(2026))
    st.divider()
    st.caption("Reporting currency: USD")
    if st.button("Log out", use_container_width=True):
        del st.session_state["user"]
        st.rerun()

records = get_year_records(user, selected_year)

if selected_page == "Executive Dashboard":
    dashboard_page(user, selected_year, records, fx_rates)
elif selected_page == "Financial Data":
    financial_data_page(user, selected_year, fx_rates)
elif selected_page == "Financial Consolidation":
    consolidation_page(user, selected_year, fx_rates)
elif selected_page == "Planning & Forecasting":
    planning_page(user, selected_year, records, fx_rates)
elif selected_page == "Audit Trail":
    audit_page(user)
