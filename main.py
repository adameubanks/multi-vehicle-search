from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Tuple
import json
from collections import defaultdict
import heapq

app = FastAPI(title="Multi-Vehicle Storage Search API", version="1.0.0")

class VehicleRequest(BaseModel):
    length: int = Field(..., gt=0, description="Length of vehicle in feet")
    quantity: int = Field(..., gt=0, le=5, description="Number of vehicles of this size")

class Listing(BaseModel):
    id: str
    location_id: str
    length: int
    width: int
    price_in_cents: int

class LocationResult(BaseModel):
    location_id: str
    listing_ids: List[str]
    total_price_in_cents: int

# Load listings data
with open('listings.json', 'r') as f:
    listings_data = json.load(f)
    listings = [Listing(**listing) for listing in listings_data]

def can_fit_vehicle(vehicle_length: int, vehicle_width: int, listing: Listing) -> bool:
    """Check if a vehicle can fit in a listing (considering orientation)"""
    return (vehicle_length <= listing.length and vehicle_width <= listing.width) or \
           (vehicle_length <= listing.width and vehicle_width <= listing.length)

def calculate_waste(vehicle_length: int, vehicle_width: int, listing: Listing) -> int:
    """Calculate wasted space when placing vehicle in listing"""
    if vehicle_length <= listing.length and vehicle_width <= listing.width:
        return listing.length * listing.width - vehicle_length * vehicle_width
    elif vehicle_length <= listing.width and vehicle_width <= listing.length:
        return listing.length * listing.width - vehicle_length * vehicle_width
    return float('inf')

def decreasing_best_fit_heuristic(vehicles: List[VehicleRequest]) -> List[LocationResult]:
    """Decreasing best-fit with multi-vehicle-per-listing packing.

    Each listing fixes an orientation on first use and exposes columns of width 10.
    Vehicles are placed into columns by greedily choosing the smallest leftover length.
    """
    # Expand vehicles by quantity and sort by length (descending)
    expanded_vehicles = []
    for vehicle in vehicles:
        for _ in range(vehicle.quantity):
            expanded_vehicles.append((vehicle.length, 10))

    expanded_vehicles.sort(key=lambda x: x[0], reverse=True)

    # Group listings by location
    listings_by_location = defaultdict(list)
    for listing in listings:
        listings_by_location[listing.location_id].append(listing)

    results = []

    for location_id, location_listings in listings_by_location.items():
        remaining = expanded_vehicles.copy()
        used_listing_ids = set()
        # listing_id -> { 'listing': Listing, 'orientation': 'LW'|'WL', 'columns': List[int], 'col_capacity': int }
        open_states: Dict[str, Dict] = {}

        def eval_open_fit(vehicle_len: int) -> Tuple[str, int, int]:
            # returns (listing_id, col_idx, leftover) with minimal leftover, or (None, -1, inf)
            best = (None, -1, float('inf'))
            for lid, state in open_states.items():
                for idx, cap in enumerate(state['columns']):
                    if cap >= vehicle_len:
                        leftover = cap - vehicle_len
                        if leftover < best[2]:
                            best = (lid, idx, leftover)
            return best

        def choose_orientation_for_first_vehicle(listing: Listing, vehicle_len: int) -> Tuple[str, int, int]:
            # returns (orientation, num_cols, col_capacity) or (None, 0, 0) if not feasible
            ori_candidates = []
            # orientation 'LW': place along length, columns across width
            cols_LW = listing.width // 10
            cap_LW = listing.length
            if cols_LW >= 1 and cap_LW >= vehicle_len:
                ori_candidates.append(('LW', cols_LW, cap_LW, cap_LW - vehicle_len))
            # orientation 'WL': place along width, columns across length
            cols_WL = listing.length // 10
            cap_WL = listing.width
            if cols_WL >= 1 and cap_WL >= vehicle_len:
                ori_candidates.append(('WL', cols_WL, cap_WL, cap_WL - vehicle_len))
            if not ori_candidates:
                return (None, 0, 0)
            # prefer smallest leftover; tie-break by more columns
            ori_candidates.sort(key=lambda x: (x[3], -x[1]))
            best = ori_candidates[0]
            return (best[0], best[1], best[2])

        def eval_new_listing(vehicle_len: int) -> Tuple[str, int]:
            # returns (listing_id, leftover_after_placing_in_new) with minimal leftover; (None, inf) if none
            best_id = None
            best_leftover = float('inf')
            best_price = float('inf')
            for listing in location_listings:
                if listing.id in used_listing_ids:
                    continue
                ori, num_cols, col_cap = choose_orientation_for_first_vehicle(listing, vehicle_len)
                if ori is None:
                    continue
                leftover = col_cap - vehicle_len
                if leftover < best_leftover or (leftover == best_leftover and listing.price_in_cents < best_price):
                    best_leftover = leftover
                    best_price = listing.price_in_cents
                    best_id = listing.id
            return (best_id, best_leftover)

        # Greedy placement loop
        success = True
        while remaining:
            vlen, _ = remaining[0]
            lid, col_idx, leftover = eval_open_fit(vlen)
            if lid is not None:
                # place into existing state
                open_states[lid]['columns'][col_idx] -= vlen
                remaining.pop(0)
                continue
            # need to open a new listing
            new_lid, _ = eval_new_listing(vlen)
            if new_lid is None:
                success = False
                break
            # initialize state and place vehicle into best column (all equal at start)
            listing = next(l for l in location_listings if l.id == new_lid)
            ori, num_cols, col_cap = choose_orientation_for_first_vehicle(listing, vlen)
            state = {
                'listing': listing,
                'orientation': ori,
                'columns': [col_cap] * num_cols,
            }
            # place into first column (all equal), reduce capacity
            state['columns'][0] -= vlen
            open_states[new_lid] = state
            used_listing_ids.add(new_lid)
            remaining.pop(0)

        if success and not remaining:
            listing_ids = list(used_listing_ids)
            total_price = sum(open_states[lid]['listing'].price_in_cents for lid in listing_ids)
            results.append(LocationResult(
                location_id=location_id,
                listing_ids=listing_ids,
                total_price_in_cents=total_price
            ))

    results.sort(key=lambda x: x.total_price_in_cents)
    return results

@app.post("/", response_model=List[LocationResult])
async def search_storage(request: List[VehicleRequest]):
    """Search for storage locations that can accommodate all requested vehicles"""
    
    # Validate total quantity constraint
    total_quantity = sum(vehicle.quantity for vehicle in request)
    if total_quantity > 5:
        raise HTTPException(status_code=400, detail="Total quantity cannot exceed 5 vehicles")
    
    if total_quantity == 0:
        return []
    
    # Validate vehicle dimensions
    for vehicle in request:
        if vehicle.length <= 0:
            raise HTTPException(status_code=400, detail="Vehicle length must be positive")
    
    try:
        results = decreasing_best_fit_heuristic(request)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "listings_count": len(listings)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
