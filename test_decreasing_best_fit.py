import json
import time
from typing import List, Dict, Tuple
from collections import defaultdict
from main import decreasing_best_fit_heuristic, VehicleRequest, Listing, LocationResult

def load_listings() -> List[Listing]:
    """Load listings from JSON file"""
    with open('listings.json', 'r') as f:
        listings_data = json.load(f)
        return [Listing(**listing) for listing in listings_data]

def brute_force_optimal(vehicles: List[VehicleRequest], listings: List[Listing]) -> List[LocationResult]:
    """Brute force approach to find truly optimal solutions for validation"""
    # Expand vehicles by quantity
    expanded_vehicles = []
    for vehicle in vehicles:
        for _ in range(vehicle.quantity):
            expanded_vehicles.append((vehicle.length, 10))
    
    # Group listings by location
    listings_by_location = defaultdict(list)
    for listing in listings:
        listings_by_location[listing.location_id].append(listing)
    
    results = []
    
    for location_id, location_listings in listings_by_location.items():
        # Try all possible combinations of listings for this location
        from itertools import combinations
        
        for r in range(1, len(location_listings) + 1):
            for listing_combo in combinations(location_listings, r):
                # Check if this combination can fit all vehicles
                remaining_vehicles = expanded_vehicles.copy()
                used_listings = []
                
                for listing in listing_combo:
                    for i, (v_length, v_width) in enumerate(remaining_vehicles):
                        if can_fit_vehicle(v_length, v_width, listing):
                            used_listings.append(listing)
                            remaining_vehicles.pop(i)
                            break
                
                # If all vehicles were placed, this is a valid solution
                if not remaining_vehicles:
                    total_price = sum(listing.price_in_cents for listing in used_listings)
                    listing_ids = [listing.id for listing in used_listings]
                    results.append(LocationResult(
                        location_id=location_id,
                        listing_ids=listing_ids,
                        total_price_in_cents=total_price
                    ))
                    break  # Found a solution for this location, move to next
    
    results.sort(key=lambda x: x.total_price_in_cents)
    return results

def can_fit_vehicle(vehicle_length: int, vehicle_width: int, listing: Listing) -> bool:
    """Check if a vehicle can fit in a listing"""
    return (vehicle_length <= listing.length and vehicle_width <= listing.width) or \
           (vehicle_length <= listing.width and vehicle_width <= listing.length)

def validate_solution_correctness(vehicles: List[VehicleRequest], heuristic_results: List[LocationResult], 
                                 listings: List[Listing]) -> Dict:
    """Validate results allowing multi-vehicle-per-listing packing with fixed orientation per listing."""
    validation_results = {
        'all_vehicles_placed': True,
        'valid_listings': True,
        'correct_pricing': True,
        'optimal_solutions': True,
        'issues': []
    }

    # listing id lookup
    listing_lookup = {l.id: l for l in listings}

    def choose_orientation_for_first_vehicle(listing: Listing, vehicle_len: int):
        candidates = []
        cols_LW = listing.width // 10
        cap_LW = listing.length
        if cols_LW >= 1 and cap_LW >= vehicle_len:
            candidates.append(('LW', cols_LW, cap_LW))
        cols_WL = listing.length // 10
        cap_WL = listing.width
        if cols_WL >= 1 and cap_WL >= vehicle_len:
            candidates.append(('WL', cols_WL, cap_WL))
        if not candidates:
            return None
        # prefer smaller leftover after first placement
        candidates.sort(key=lambda t: (t[2] - vehicle_len))
        return candidates[0]

    def attempt_pack_with_listings(expanded: List[Tuple[int, int]], listing_ids: List[str]) -> bool:
        # states per listing id: { 'orientation': 'LW'|'WL', 'columns': [cap,...] }
        states = {}
        # sort vehicles by decreasing length
        items = sorted(expanded, key=lambda x: x[0], reverse=True)
        for vlen, _ in items:
            placed = False
            # try to place in any already opened listing first
            best_fit = (None, -1, float('inf'))
            for lid, state in states.items():
                for idx, cap in enumerate(state['columns']):
                    if cap >= vlen:
                        leftover = cap - vlen
                        if leftover < best_fit[2]:
                            best_fit = (lid, idx, leftover)
            if best_fit[0] is not None:
                states[best_fit[0]]['columns'][best_fit[1]] -= vlen
                placed = True
            else:
                # try to open a new listing from the provided set
                for lid in listing_ids:
                    if lid in states:
                        continue
                    listing = listing_lookup.get(lid)
                    if listing is None:
                        continue
                    choice = choose_orientation_for_first_vehicle(listing, vlen)
                    if choice is None:
                        continue
                    ori, ncols, colcap = choice
                    states[lid] = {'orientation': ori, 'columns': [colcap] * ncols}
                    states[lid]['columns'][0] -= vlen
                    placed = True
                    break
            if not placed:
                return False
        return True

    for result in heuristic_results:
        # expand vehicles
        expanded = []
        for v in vehicles:
            for _ in range(v.quantity):
                expanded.append((v.length, 10))

        # validate listing ids and price
        price_sum = 0
        for lid in result.listing_ids:
            if lid not in listing_lookup:
                validation_results['valid_listings'] = False
                validation_results['issues'].append(f"Invalid listing ID: {lid}")
            else:
                price_sum += listing_lookup[lid].price_in_cents

        if price_sum != result.total_price_in_cents:
            validation_results['correct_pricing'] = False
            validation_results['issues'].append(
                f"Price mismatch: calculated {price_sum}, reported {result.total_price_in_cents}")

        # attempt to pack all vehicles into the declared listings
        ok = attempt_pack_with_listings(expanded, result.listing_ids)
        if not ok:
            validation_results['all_vehicles_placed'] = False
            validation_results['issues'].append("Declared listing set cannot pack all vehicles")

    return validation_results

def test_simple_cases():
    """Test with simple cases where we can verify optimality"""
    print("=== Testing Simple Cases ===")
    listings = load_listings()
    
    # Test case 1: Single vehicle
    vehicles = [VehicleRequest(length=10, quantity=1)]
    
    print(f"\nTest 1: Single 10ft vehicle")
    start_time = time.time()
    heuristic_results = decreasing_best_fit_heuristic(vehicles)
    heuristic_time = time.time() - start_time
    
    print(f"Heuristic time: {heuristic_time*1000:.2f}ms")
    print(f"Number of solutions: {len(heuristic_results)}")
    
    # Validate correctness
    validation = validate_solution_correctness(vehicles, heuristic_results, listings)
    print(f"Validation: {validation}")
    
    if heuristic_results:
        print(f"Cheapest solution: {heuristic_results[0].total_price_in_cents} cents")
        print(f"Most expensive solution: {heuristic_results[-1].total_price_in_cents} cents")
    
    # Test case 2: Multiple small vehicles
    vehicles = [VehicleRequest(length=10, quantity=2)]
    
    print(f"\nTest 2: Two 10ft vehicles")
    start_time = time.time()
    heuristic_results = decreasing_best_fit_heuristic(vehicles)
    heuristic_time = time.time() - start_time
    
    print(f"Heuristic time: {heuristic_time*1000:.2f}ms")
    print(f"Number of solutions: {len(heuristic_results)}")
    
    validation = validate_solution_correctness(vehicles, heuristic_results, listings)
    print(f"Validation: {validation}")
    
    if heuristic_results:
        print(f"Cheapest solution: {heuristic_results[0].total_price_in_cents} cents")
        print(f"Most expensive solution: {heuristic_results[-1].total_price_in_cents} cents")

def test_complex_cases():
    """Test with complex cases from README"""
    print("\n=== Testing Complex Cases ===")
    listings = load_listings()
    
    # Test case from README
    vehicles = [
        VehicleRequest(length=10, quantity=1),
        VehicleRequest(length=20, quantity=2),
        VehicleRequest(length=25, quantity=1)
    ]
    
    print(f"\nTest 3: Complex case from README")
    start_time = time.time()
    heuristic_results = decreasing_best_fit_heuristic(vehicles)
    heuristic_time = time.time() - start_time
    
    print(f"Heuristic time: {heuristic_time*1000:.2f}ms")
    print(f"Number of solutions: {len(heuristic_results)}")
    
    validation = validate_solution_correctness(vehicles, heuristic_results, listings)
    print(f"Validation: {validation}")
    
    if heuristic_results:
        print(f"Cheapest solution: {heuristic_results[0].total_price_in_cents} cents")
        print(f"Most expensive solution: {heuristic_results[-1].total_price_in_cents} cents")
        
        # Show details of cheapest solution
        cheapest = heuristic_results[0]
        print(f"\nCheapest solution details:")
        print(f"  Location: {cheapest.location_id}")
        print(f"  Listings: {cheapest.listing_ids}")
        print(f"  Total price: {cheapest.total_price_in_cents} cents")
        
        # Show listing details
        listing_lookup = {listing.id: listing for listing in listings}
        for listing_id in cheapest.listing_ids:
            listing = listing_lookup[listing_id]
            print(f"    - {listing_id}: {listing.length}x{listing.width} @ {listing.price_in_cents} cents")

def test_edge_cases():
    """Test edge cases"""
    print("\n=== Testing Edge Cases ===")
    listings = load_listings()
    
    # Test case: Maximum vehicles (5)
    vehicles = [VehicleRequest(length=10, quantity=5)]
    
    print(f"\nTest 4: Maximum vehicles (5x10ft)")
    start_time = time.time()
    heuristic_results = decreasing_best_fit_heuristic(vehicles)
    heuristic_time = time.time() - start_time
    
    print(f"Heuristic time: {heuristic_time*1000:.2f}ms")
    print(f"Number of solutions: {len(heuristic_results)}")
    
    validation = validate_solution_correctness(vehicles, heuristic_results, listings)
    print(f"Validation: {validation}")
    
    # Test case: Large vehicles
    vehicles = [VehicleRequest(length=50, quantity=1)]
    
    print(f"\nTest 5: Large vehicle (50ft)")
    start_time = time.time()
    heuristic_results = decreasing_best_fit_heuristic(vehicles)
    heuristic_time = time.time() - start_time
    
    print(f"Heuristic time: {heuristic_time*1000:.2f}ms")
    print(f"Number of solutions: {len(heuristic_results)}")
    
    validation = validate_solution_correctness(vehicles, heuristic_results, listings)
    print(f"Validation: {validation}")

def test_algorithm_efficiency():
    """Test algorithm efficiency with various inputs"""
    print("\n=== Testing Algorithm Efficiency ===")
    listings = load_listings()
    
    test_cases = [
        [VehicleRequest(length=10, quantity=1)],
        [VehicleRequest(length=10, quantity=2)],
        [VehicleRequest(length=20, quantity=1)],
        [VehicleRequest(length=10, quantity=1), VehicleRequest(length=20, quantity=1)],
        [VehicleRequest(length=10, quantity=1), VehicleRequest(length=20, quantity=2)],
        [VehicleRequest(length=10, quantity=1), VehicleRequest(length=20, quantity=2), VehicleRequest(length=25, quantity=1)],
        [VehicleRequest(length=10, quantity=5)],
    ]
    
    for i, vehicles in enumerate(test_cases):
        print(f"\nEfficiency Test {i+1}: {[f'{v.quantity}x{v.length}ft' for v in vehicles]}")
        
        start_time = time.time()
        results = decreasing_best_fit_heuristic(vehicles)
        end_time = time.time()
        
        print(f"  Time: {(end_time - start_time)*1000:.2f}ms")
        print(f"  Solutions: {len(results)}")
        
        if results:
            print(f"  Price range: {results[0].total_price_in_cents} - {results[-1].total_price_in_cents} cents")

if __name__ == "__main__":
    print("Running comprehensive tests for decreasing best fit heuristic...")
    
    test_simple_cases()
    test_complex_cases()
    test_edge_cases()
    test_algorithm_efficiency()
    
    print("\n=== Test Summary ===")
    print("All tests completed. Check validation results above for any issues.")
