"""
Tests for restock order API endpoints and the forecast fields they depend on.
"""
from datetime import date, timedelta

import pytest

import mock_data


@pytest.fixture(autouse=True)
def reset_restock_orders():
    """Restock orders live in module memory; clear them so each test is independent."""
    mock_data.restock_orders.clear()
    yield
    mock_data.restock_orders.clear()


def get_forecasts_by_sku(client):
    response = client.get("/api/demand")
    assert response.status_code == 200
    return {f["item_sku"]: f for f in response.json()}


class TestRestockForecastFields:
    """Test the cost and lead-time fields added to demand forecasts."""

    def test_demand_forecast_cost_and_lead_time_types(self, client):
        """Test that every forecast has a positive unit_cost and lead_time_days."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for forecast in data:
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] > 0
            assert isinstance(forecast["lead_time_days"], int)
            assert 5 <= forecast["lead_time_days"] <= 21


class TestRestockOrderEndpoints:
    """Test suite for restock order endpoints."""

    def test_get_all_restock_orders_empty(self, client):
        """Test that the restock order list starts empty."""
        response = client.get("/api/restock-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_restock_order(self, client):
        """Test a successful order: server-computed total, longest lead time, delivery date."""
        forecasts = get_forecasts_by_sku(client)
        lines = [{"sku": "WDG-001", "quantity": 10}, {"sku": "FLT-405", "quantity": 20}]
        expected_total = sum(forecasts[l["sku"]]["unit_cost"] * l["quantity"] for l in lines)
        expected_lead = max(forecasts[l["sku"]]["lead_time_days"] for l in lines)

        response = client.post("/api/restock-orders", json={"items": lines, "budget": 100000})
        assert response.status_code == 201

        order = response.json()
        assert order["order_number"].startswith("RST-")
        assert order["status"] == "Submitted"
        assert abs(order["total_cost"] - expected_total) < 0.01
        assert order["lead_time_days"] == expected_lead
        assert order["expected_delivery"] == (date.today() + timedelta(days=expected_lead)).isoformat()

        assert len(order["items"]) == 2
        for item in order["items"]:
            assert item["name"] == forecasts[item["sku"]]["item_name"]
            assert item["unit_cost"] == forecasts[item["sku"]]["unit_cost"]

    def test_created_restock_order_appears_in_list_newest_first(self, client):
        """Test that created orders are returned by GET, newest first."""
        first = client.post("/api/restock-orders", json={"items": [{"sku": "WDG-001", "quantity": 1}], "budget": 1000})
        second = client.post("/api/restock-orders", json={"items": [{"sku": "GSK-203", "quantity": 1}], "budget": 1000})
        assert first.status_code == 201
        assert second.status_code == 201

        response = client.get("/api/restock-orders")
        assert response.status_code == 200

        data = response.json()
        assert [o["order_number"] for o in data] == [
            second.json()["order_number"],
            first.json()["order_number"],
        ]

    def test_create_restock_order_unknown_sku(self, client):
        """Test that an unknown SKU returns 400."""
        response = client.post("/api/restock-orders", json={"items": [{"sku": "NOPE-999", "quantity": 1}], "budget": 1000})
        assert response.status_code == 400
        assert "NOPE-999" in response.json()["detail"]

    def test_create_restock_order_empty_items(self, client):
        """Test that an order with no items returns 400."""
        response = client.post("/api/restock-orders", json={"items": [], "budget": 1000})
        assert response.status_code == 400
        assert "detail" in response.json()

    def test_create_restock_order_non_positive_quantity(self, client):
        """Test that a quantity of 0 returns 400."""
        response = client.post("/api/restock-orders", json={"items": [{"sku": "WDG-001", "quantity": 0}], "budget": 1000})
        assert response.status_code == 400

    def test_create_restock_order_negative_quantity(self, client):
        """Test that a negative quantity returns 400."""
        response = client.post("/api/restock-orders", json={"items": [{"sku": "WDG-001", "quantity": -5}], "budget": 1000})
        assert response.status_code == 400

    def test_create_restock_order_duplicate_sku(self, client):
        """Test that the same SKU twice in one order returns 400."""
        lines = [{"sku": "WDG-001", "quantity": 1}, {"sku": "WDG-001", "quantity": 2}]
        response = client.post("/api/restock-orders", json={"items": lines, "budget": 1000})
        assert response.status_code == 400
        assert "WDG-001" in response.json()["detail"]

    def test_create_restock_order_exactly_at_budget(self, client):
        """Test that an order costing exactly the budget is accepted."""
        unit_cost = get_forecasts_by_sku(client)["FLT-405"]["unit_cost"]
        budget = round(unit_cost * 3, 2)
        response = client.post("/api/restock-orders", json={"items": [{"sku": "FLT-405", "quantity": 3}], "budget": budget})
        assert response.status_code == 201

    def test_create_restock_order_invalid_budget(self, client):
        """Test that a negative or NaN budget is rejected and cannot bypass the budget check."""
        line = [{"sku": "WDG-001", "quantity": 1}]
        assert client.post("/api/restock-orders", json={"items": line, "budget": -1}).status_code == 400

        body = '{"items": [{"sku": "WDG-001", "quantity": 100}], "budget": NaN}'
        response = client.post("/api/restock-orders", content=body, headers={"Content-Type": "application/json"})
        assert response.status_code == 400
        assert client.get("/api/restock-orders").json() == []

    def test_create_restock_order_over_budget(self, client):
        """Test that an order costing more than the budget returns 400 and is not stored."""
        response = client.post("/api/restock-orders", json={"items": [{"sku": "WDG-001", "quantity": 100}], "budget": 10})
        assert response.status_code == 400
        assert "budget" in response.json()["detail"].lower()

        assert client.get("/api/restock-orders").json() == []
