"""
Tests for reports API endpoints (quarterly performance and monthly trends).
"""
import pytest


QUARTERLY_FIELDS = ["quarter", "total_orders", "total_revenue", "delivered_orders",
                    "avg_order_value", "fulfillment_rate"]
MONTHLY_FIELDS = ["month", "order_count", "revenue", "delivered_count"]


def has_at_most_two_decimals(value):
    return abs(round(value, 2) - value) < 1e-9 and len(repr(value).split(".")[-1]) <= 2


class TestQuarterlyReports:
    """Test suite for the quarterly reports endpoint."""

    def test_get_quarterly_reports(self, client):
        """Test getting all quarterly reports."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        for row in data:
            for field in QUARTERLY_FIELDS:
                assert field in row

    def test_quarterly_reports_sorted(self, client):
        """Test that quarters are returned in ascending order."""
        data = client.get("/api/reports/quarterly").json()
        quarters = [q["quarter"] for q in data]
        assert quarters == sorted(quarters)

    def test_quarterly_totals_match_orders(self, client):
        """Test that quarterly order counts add up to the full order list."""
        orders = client.get("/api/orders").json()
        data = client.get("/api/reports/quarterly").json()
        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_quarterly_calculations(self, client):
        """Test that averages and fulfillment rates are derived correctly."""
        data = client.get("/api/reports/quarterly").json()
        for q in data:
            assert abs(q["avg_order_value"] - q["total_revenue"] / q["total_orders"]) < 0.01
            expected_rate = round(q["delivered_orders"] / q["total_orders"] * 100, 1)
            assert q["fulfillment_rate"] == expected_rate

    def test_quarterly_money_is_rounded(self, client):
        """Test that money values carry no floating point noise."""
        data = client.get("/api/reports/quarterly").json()
        for q in data:
            assert has_at_most_two_decimals(q["total_revenue"])
            assert has_at_most_two_decimals(q["avg_order_value"])

    def test_get_quarterly_reports_by_warehouse(self, client):
        """Test that the warehouse filter is applied to quarterly reports."""
        tokyo_orders = client.get("/api/orders?warehouse=Tokyo").json()
        data = client.get("/api/reports/quarterly?warehouse=Tokyo").json()

        assert sum(q["total_orders"] for q in data) == len(tokyo_orders)
        all_total = sum(q["total_orders"] for q in client.get("/api/reports/quarterly").json())
        assert sum(q["total_orders"] for q in data) < all_total

    def test_get_quarterly_reports_by_quarter(self, client):
        """Test that a quarter filter returns only that quarter."""
        data = client.get("/api/reports/quarterly?month=Q2-2025").json()
        assert [q["quarter"] for q in data] == ["Q2-2025"]

    def test_get_quarterly_reports_multiple_filters(self, client):
        """Test that combined filters match the orders endpoint."""
        query = "warehouse=San Francisco&category=Sensors&status=Delivered"
        orders = client.get(f"/api/orders?{query}").json()
        data = client.get(f"/api/reports/quarterly?{query}").json()

        assert sum(q["total_orders"] for q in data) == len(orders)
        for q in data:
            assert q["fulfillment_rate"] == 100.0

    def test_get_quarterly_reports_no_matches(self, client):
        """Test that a filter matching nothing returns an empty list."""
        response = client.get("/api/reports/quarterly?warehouse=Nowhere")
        assert response.status_code == 200
        assert response.json() == []


class TestMonthlyTrends:
    """Test suite for the monthly trends endpoint."""

    def test_get_monthly_trends(self, client):
        """Test getting all monthly trends."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        for row in data:
            for field in MONTHLY_FIELDS:
                assert field in row
            assert len(row["month"]) == 7 and row["month"][4] == "-"

    def test_monthly_trends_sorted(self, client):
        """Test that months are returned in ascending order."""
        months = [m["month"] for m in client.get("/api/reports/monthly-trends").json()]
        assert months == sorted(months)

    def test_monthly_revenue_is_rounded(self, client):
        """Test that monthly revenue carries no floating point noise."""
        for m in client.get("/api/reports/monthly-trends").json():
            assert has_at_most_two_decimals(m["revenue"])

    def test_monthly_matches_quarterly(self, client):
        """Test that monthly and quarterly reports agree on totals."""
        monthly = client.get("/api/reports/monthly-trends").json()
        quarterly = client.get("/api/reports/quarterly").json()

        assert sum(m["order_count"] for m in monthly) == sum(q["total_orders"] for q in quarterly)
        assert abs(sum(m["revenue"] for m in monthly) - sum(q["total_revenue"] for q in quarterly)) < 0.05

    def test_get_monthly_trends_by_month(self, client):
        """Test that a single-month filter returns only that month."""
        data = client.get("/api/reports/monthly-trends?month=2025-03").json()
        assert [m["month"] for m in data] == ["2025-03"]

    def test_get_monthly_trends_by_category(self, client):
        """Test that the category filter is applied to monthly trends."""
        orders = client.get("/api/orders?category=Actuators").json()
        data = client.get("/api/reports/monthly-trends?category=Actuators").json()
        assert sum(m["order_count"] for m in data) == len(orders)

    def test_get_monthly_trends_all_filter_value(self, client):
        """Test that 'all' filter values behave like no filter."""
        unfiltered = client.get("/api/reports/monthly-trends").json()
        all_values = client.get(
            "/api/reports/monthly-trends?warehouse=all&category=all&status=all&month=all"
        ).json()
        assert unfiltered == all_values
