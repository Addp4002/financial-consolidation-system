def build_forecast(
    revenue: float,
    operating_expenses: float,
    revenue_growth_pct: float,
    expense_inflation_pct: float,
) -> dict[str, float]:
    projected_revenue = float(revenue) * (1 + float(revenue_growth_pct) / 100)
    projected_expenses = float(operating_expenses) * (1 + float(expense_inflation_pct) / 100)
    projected_profit = projected_revenue - projected_expenses
    projected_margin = (projected_profit / projected_revenue * 100) if projected_revenue else 0.0
    return {
        "projected_revenue": projected_revenue,
        "projected_expenses": projected_expenses,
        "projected_profit": projected_profit,
        "projected_margin_pct": projected_margin,
    }
