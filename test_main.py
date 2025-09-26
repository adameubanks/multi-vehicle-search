import pytest
from fastapi.testclient import TestClient
from main import app, find_best_fit_decreasing, can_fit_vehicle, calculate_waste

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_single_vehicle_search():
    response = client.post("/", json=[{"length": 10, "quantity": 1}])
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    assert all("location_id" in result for result in results)
    assert all("listing_ids" in result for result in results)
    assert all("total_price_in_cents" in result for result in results)

def test_multiple_vehicles_search():
    response = client.post("/", json=[
        {"length": 10, "quantity": 1},
        {"length": 20, "quantity": 2}
    ])
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0

def test_max_quantity_validation():
    response = client.post("/", json=[
        {"length": 10, "quantity": 3},
        {"length": 20, "quantity": 3}
    ])
    assert response.status_code == 400
    assert "Total quantity cannot exceed 5" in response.json()["detail"]

def test_vehicle_length_validation():
    response = client.post("/", json=[{"length": 15, "quantity": 1}])
    assert response.status_code == 422

def test_quantity_validation():
    response = client.post("/", json=[{"length": 10, "quantity": 0}])
    assert response.status_code == 422

def test_can_fit_vehicle():
    listing = {"length": 20, "width": 15}
    assert can_fit_vehicle(listing, 10) == True
    assert can_fit_vehicle(listing, 25) == False
    assert can_fit_vehicle(listing, 20) == True

def test_calculate_waste():
    listing = {"length": 20, "width": 15}
    waste = calculate_waste(listing, 10)
    assert waste == 150

def test_find_best_fit_decreasing():
    vehicles = [{"length": 10, "quantity": 1}]
    listings = [
        {"id": "1", "length": 20, "width": 15, "price_in_cents": 100},
        {"id": "2", "length": 10, "width": 10, "price_in_cents": 50}
    ]
    
    result = find_best_fit_decreasing(vehicles, listings)
    assert result is not None
    assert result["total_price_in_cents"] == 50
    assert "2" in result["listing_ids"]

def test_no_solution():
    vehicles = [{"length": 100, "quantity": 1}]
    listings = [
        {"id": "1", "length": 20, "width": 15, "price_in_cents": 100}
    ]
    
    result = find_best_fit_decreasing(vehicles, listings)
    assert result is None

def test_results_sorted_by_price():
    response = client.post("/", json=[{"length": 10, "quantity": 1}])
    assert response.status_code == 200
    results = response.json()
    
    prices = [result["total_price_in_cents"] for result in results]
    assert prices == sorted(prices)

if __name__ == "__main__":
    pytest.main([__file__])
