import unittest

from services.auth import allowed_countries, can_access_country
from services.consolidation import consolidate_records
from services.forecast import build_forecast


class AccessControlTests(unittest.TestCase):
    def test_group_cfo_can_access_all_entities(self):
        user = {"role": "Group_CFO", "country": None, "region": None}
        self.assertEqual(set(allowed_countries(user)), {"India", "USA", "Germany"})

    def test_us_manager_cannot_access_india(self):
        user = {"role": "Country_Finance_Manager", "country": "USA", "region": "Americas"}
        self.assertTrue(can_access_country(user, "USA"))
        self.assertFalse(can_access_country(user, "India"))

    def test_regional_controller_is_scoped_to_region(self):
        user = {"role": "Regional_Controller", "country": None, "region": "Americas"}
        self.assertEqual(allowed_countries(user), ["USA"])


class FinanceCalculationTests(unittest.TestCase):
    def test_intercompany_eliminations_are_applied(self):
        rows = [
            {
                "country": "USA", "currency": "USD", "revenue": 1000,
                "operating_expenses": 700, "intercompany_revenue": 100,
                "intercompany_expenses": 50,
            },
            {
                "country": "Germany", "currency": "EUR", "revenue": 1000,
                "operating_expenses": 600, "intercompany_revenue": 100,
                "intercompany_expenses": 150,
            },
        ]
        result = consolidate_records(rows, {"USD": 1.0, "EUR": 1.0})
        self.assertEqual(result["consolidated_revenue_usd"], 1800)
        self.assertEqual(result["consolidated_opex_usd"], 1100)
        self.assertEqual(result["net_profit_usd"], 700)
        self.assertEqual(result["ic_reconciliation_difference_usd"], 0)

    def test_forecast_uses_separate_growth_and_inflation_assumptions(self):
        result = build_forecast(1000, 600, 10, 5)
        self.assertAlmostEqual(result["projected_revenue"], 1100)
        self.assertAlmostEqual(result["projected_expenses"], 630)
        self.assertAlmostEqual(result["projected_profit"], 470)


if __name__ == "__main__":
    unittest.main()
