from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Tuple
import json
from collections import defaultdict
import heapq

app = FastAPI()

class VehicleRequest(BaseModel):
    length: int = Field(gt=0, multiple_of=10)
    quantity: int = Field(gt=0, le=5)

class SearchResult(BaseModel):
    location_id: str
    listing_ids: List[str]
    total_price_in_cents: int

listings_by_location = {}

@app.on_event("startup")
async def load_listings():
    global listings_by_location
    with open("listings.json", "r") as f:
        listings = json.load(f)
    
    for listing in listings:
        location_id = listing["location_id"]
        if location_id not in listings_by_location:
            listings_by_location[location_id] = []
        listings_by_location[location_id].append(listing)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@app.post("/", response_model=List[SearchResult])
async def search_vehicles(vehicles: List[VehicleRequest]):
    if sum(v.quantity for v in vehicles) > 5:
        raise HTTPException(status_code=400, detail="Total quantity cannot exceed 5")
    
    results = []
    
    for location_id, listings in listings_by_location.items():
        solution = find_best_fit_decreasing(vehicles, listings)
        if solution:
            results.append(SearchResult(
                location_id=location_id,
                listing_ids=solution["listing_ids"],
                total_price_in_cents=solution["total_price_in_cents"]
            ))
    
    results.sort(key=lambda x: x.total_price_in_cents)
    return results

def find_best_fit_decreasing(vehicles: List[VehicleRequest], listings: List[Dict]) -> Dict:
    vehicle_demands = []
    for v in vehicles:
        for _ in range(v.quantity):
            vehicle_demands.append(v.length)
    
    vehicle_demands.sort(reverse=True)
    
    used_listings = []
    remaining_demands = vehicle_demands.copy()
    
    for demand in vehicle_demands:
        if not remaining_demands or demand not in remaining_demands:
            continue
            
        best_listing = None
        best_waste = float('inf')
        
        for listing in listings:
            if can_fit_vehicle(listing, demand):
                waste = calculate_waste(listing, demand)
                if waste < best_waste:
                    best_waste = waste
                    best_listing = listing
        
        if best_listing:
            used_listings.append(best_listing)
            remaining_demands.remove(demand)
    
    if remaining_demands:
        return None
    
    return {
        "listing_ids": [listing["id"] for listing in used_listings],
        "total_price_in_cents": sum(listing["price_in_cents"] for listing in used_listings)
    }

def can_fit_vehicle(listing: Dict, vehicle_length: int) -> bool:
    return (listing["length"] >= vehicle_length and 
            listing["width"] >= 10)

def calculate_waste(listing: Dict, vehicle_length: int) -> int:
    return (listing["length"] - vehicle_length) * listing["width"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
