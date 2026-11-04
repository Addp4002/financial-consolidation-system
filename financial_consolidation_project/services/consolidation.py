from collections import defaultdict


def convert_amount(amount: float, currency: str, fx_rates: dict[str, float]) -> float:
    rate = fx_rates.get(currency)
    if rate is None:
        raise ValueError(f"No USD conversion rate is configured for {currency}.")
    return float(amount) * float(rate)


def consolidate_records(records: list[dict], fx_rates: dict[str, float]) -> dict:
    """Convert local-currency balances to USD and apply intercompany eliminations."""
    by_country = defaultdict(lambda: {
        "country": "", "currency": "", "revenue_usd": 0.0,
        "operating_expenses_usd": 0.0, "ic_revenue_usd": 0.0,
        "ic_expenses_usd": 0.0,
    })

    gross_revenue = 0.0
    gross_opex = 0.0
    total_ic_revenue = 0.0
    total_ic_expenses = 0.0

    for row in records:
        currency = row["currency"]
        country = row["country"]
        revenue = convert_amount(row["revenue"], currency, fx_rates)
        opex = convert_amount(row["operating_expenses"], currency, fx_rates)
        ic_revenue = convert_amount(row["intercompany_revenue"], currency, fx_rates)
        ic_expenses = convert_amount(row["intercompany_expenses"], currency, fx_rates)

        item = by_country[country]
        item["country"] = country
        item["currency"] = currency
        item["revenue_usd"] += revenue
        item["operating_expenses_usd"] += opex
        item["ic_revenue_usd"] += ic_revenue
        item["ic_expenses_usd"] += ic_expenses

        gross_revenue += revenue
        gross_opex += opex
        total_ic_revenue += ic_revenue
        total_ic_expenses += ic_expenses

    consolidated_revenue = gross_revenue - total_ic_revenue
    consolidated_opex = gross_opex - total_ic_expenses
    net_profit = consolidated_revenue - consolidated_opex
    margin = (net_profit / consolidated_revenue * 100.0) if consolidated_revenue else 0.0

    country_rows = []
    for item in by_country.values():
        adjusted_revenue = item["revenue_usd"] - item["ic_revenue_usd"]
        adjusted_expenses = item["operating_expenses_usd"] - item["ic_expenses_usd"]
        item["net_profit_usd"] = adjusted_revenue - adjusted_expenses
        country_rows.append(item)

    country_rows.sort(key=lambda x: x["country"])
    return {
        "countries": country_rows,
        "gross_revenue_usd": gross_revenue,
        "gross_opex_usd": gross_opex,
        "ic_revenue_elimination_usd": total_ic_revenue,
        "ic_expense_elimination_usd": total_ic_expenses,
        "consolidated_revenue_usd": consolidated_revenue,
        "consolidated_opex_usd": consolidated_opex,
        "net_profit_usd": net_profit,
        "net_profit_margin_pct": margin,
        "ic_reconciliation_difference_usd": total_ic_revenue - total_ic_expenses,
    }
