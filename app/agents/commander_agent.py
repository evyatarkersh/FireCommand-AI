import math
import time

import pulp
import requests
from pyproj import Geod
from shapely.geometry import shape

from app.extensions import db
from app.models.fire_events import FireEvent


class CommanderAgent:
    """Commander Agent performs resource optimization based on defense line production rates and operational Suppression Difficulty Index (SDI), implementing a global time-space allocation loop for fire event response."""

    # Base production rates (meters of defense line per hour)
    BASE_PRODUCTION_RATES = {
        "ROTEM": 800.0,  # Mobile attack (Pump-and-Roll)
        "SAAR": 300.0,  # Slow sprinkler deployment in field
        "AIR_TRACTOR": 2000.0,  # Fast aerial drop
        "ESHED": 0.0  # Enabler - does not build fire line by itself
    }

    @staticmethod
    def _calculate_distance(lat1, lon1, lat2, lon2):
        """Calculate aerial distance in kilometers between two geographic coordinates using the Haversine formula, which accounts for Earth's spherical shape."""
        R = 6371.0  # Earth's radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(
            dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def __init__(self):
        """Initialize the Commander Agent with a geoid object for precise Earth surface distance calculations (WGS84 ellipsoid) and a persistent HTTP session for external API calls."""
        self.geod = Geod(ellps="WGS84")
        self.http_session = requests.Session()

    def step1_calculate_demands(self):
        """Iterate over all active fire events with prediction polygons, calculate the polygon perimeter in meters to determine defense line requirements, and persist the demand values to the database."""
        print("\n👨‍✈️ Commander Agent (Step 1): Scanning polygons and calculating defense line requirements...")

        active_events = FireEvent.query.filter(
            FireEvent.is_active == True,
            FireEvent.prediction_polygon.isnot(None)
        ).all()

        if not active_events:
            print("   💤 No active events with predictions to calculate demand at this time.")
            return

        events_updated = 0
        for event in active_events:
            try:
                # Extract geometry (coordinates) from the polygon
                polygon_geom = shape(event.prediction_polygon)

                # Calculate actual perimeter in meters
                perimeter_meters = self.geod.geometry_length(polygon_geom)

                # Save the demand requirement for the event in the database
                event.demand_perimeter_m = round(perimeter_meters, 1)
                events_updated += 1

                print(f"   🎯 Event {event.id}: Demand set to {event.demand_perimeter_m} meters.")

            except Exception as e:
                print(f"   ⚠️ Error calculating demand for event {event.id}: {e}")

        # Centralized database save
        if events_updated > 0:
            try:
                db.session.commit()
                print("   💾 Commander: All perimeter demands saved to DB successfully!")
            except Exception as e:
                db.session.rollback()
                print(f"   ❌ Commander Error (Commit Fail): {e}")

    def _determine_terrain(self, fuel_type):
        """Identify whether the terrain is urban or open forest based on the fuel type classification."""
        if fuel_type in ["Built Area"]:
            return "URBAN"
        return "FOREST"

    def _calculate_sdi_factor(self, resource_type, terrain, slope):
        """Calculate the Suppression Difficulty Index (SDI) factor (between 0.0 and 1.0) that determines how effective a resource is under current terrain and slope conditions."""
        is_steep = slope > 15.0

        if terrain == "FOREST":
            if is_steep:
                matrix = {"ROTEM": 0.7, "SAAR": 0.0, "AIR_TRACTOR": 0.9, "ESHED": 0.0}
            else:
                matrix = {"ROTEM": 1.0, "SAAR": 0.4, "AIR_TRACTOR": 1.0, "ESHED": 0.5}
        elif terrain == "URBAN":
            matrix = {"ROTEM": 0.5, "SAAR": 1.0, "AIR_TRACTOR": 0.0, "ESHED": 1.0}
        else:
            # Fallback to full effectiveness if terrain type is unknown
            matrix = {"ROTEM": 1.0, "SAAR": 1.0, "AIR_TRACTOR": 1.0, "ESHED": 1.0}

        return matrix.get(resource_type, 0.0)

    def get_actual_yield(self, resource_type, event):
        """Calculate the actual defense line production rate (meters per hour) of a specific resource type at a specific fire event, accounting for terrain and slope difficulty factors."""
        terrain = self._determine_terrain(event.fuel_type)
        slope = 0.0 if event.topo_slope is None else event.topo_slope

        base_rate = self.BASE_PRODUCTION_RATES.get(resource_type, 0.0)
        sdi_factor = self._calculate_sdi_factor(resource_type, terrain, slope)

        return base_rate * sdi_factor

    def get_net_yield(self, resource_type, event, eta_hours, time_horizon_hours):
        """Calculate net defense line production by deducting travel time from the total time horizon, returning the effective meters of defense line that can be built."""
        if eta_hours >= time_horizon_hours:
            return 0.0
        working_time_hours = time_horizon_hours - eta_hours
        actual_hourly_yield = self.get_actual_yield(resource_type, event)
        return round(actual_hourly_yield * working_time_hours, 1)

    def _fetch_available_resources(self):
        """Fetch all available resources from the database organized by type, using eager loading (joinedload) to prevent N+1 query problems when accessing station data."""
        from app.models.resources import Resource
        from sqlalchemy.orm import joinedload

        available_resources = Resource.query.options(
            joinedload(Resource.station)
        ).filter_by(status='AVAILABLE').all()

        supply = {"SAAR": [], "ESHED": [], "ROTEM": [], "AIR_TRACTOR": []}
        for res in available_resources:
            if res.resource_type in supply:
                supply[res.resource_type].append(res)

        return supply

    def _allocate_enabler_eshed(self, fire, available_esheds, allocated_set):
        """Find and assign the closest available ESHED water tanker to support SAAR vehicles at a fire event, updating its status to EN_ROUTE and tracking it in the allocated set."""
        closest_eshed = None
        min_dist = float('inf')

        # Search for the closest ESHED that hasn't been assigned yet
        for eshed in available_esheds:
            if eshed.id in allocated_set or eshed.status != 'AVAILABLE':
                continue
            dist = self._calculate_distance(fire.latitude, fire.longitude, eshed.current_lat, eshed.current_lon)
            if dist < min_dist:
                min_dist = dist
                closest_eshed = eshed

        # If found an ESHED, assign it
        if closest_eshed:
            closest_eshed.status = 'EN_ROUTE'
            closest_eshed.assigned_event_id = fire.id
            allocated_set.add(closest_eshed.id)
            print(f"💧 [Enabler] Assigned ESHED vehicle from {min_dist:.1f} km to support fire {fire.id}.")
            return closest_eshed
        else:
            print(f"⚠️ Critical Warning: No available ESHED vehicles remaining to support fire {fire.id}!")
            return None

    def _assign_district_to_fire(self, fire, all_stations):
        """Find the closest fire station to the fire event and return the district name of that station for regional resource allocation."""
        closest_station = None
        min_dist = float('inf')

        for station in all_stations:
            dist = self._calculate_distance(fire.latitude, fire.longitude, station.latitude, station.longitude)
            if dist < min_dist:
                min_dist = dist
                closest_station = station

        # Return the district name, or default value if not found
        return closest_station.district if closest_station else "UNKNOWN"

    def _get_eta_matrix(self, resources, fires):
        """Calculate travel time matrix using OSRM Table API in a single centralized request for all resource-fire combinations, significantly reducing computation time with fallback to mathematical estimation if API fails."""
        matrix = {res.id: {} for res in resources}

        # Merge resources at the same station to avoid duplicate coordinates
        stations_dict = {}  # key: (lon, lat), value: list of resources at this station
        for res in resources:
            loc = (res.current_lon, res.current_lat)
            if loc not in stations_dict:
                stations_dict[loc] = []
            stations_dict[loc].append(res)

        unique_stations = list(stations_dict.keys())

        # Build coordinate array: first all stations (sources), then all fires (destinations)
        coords = [f"{lon},{lat}" for lon, lat in unique_stations]
        coords += [f"{fire.longitude},{fire.latitude}" for fire in fires]

        # Create indices for sources and destinations
        sources_indices = ";".join(str(i) for i in range(len(unique_stations)))
        dest_indices = ";".join(str(i + len(unique_stations)) for i in range(len(fires)))

        # Build URL for Table service
        coords_string = ";".join(coords)
        url = f"http://router.project-osrm.org/table/v1/driving/{coords_string}?sources={sources_indices}&destinations={dest_indices}"

        try:
            print(f"   🌐 Sending centralized OSRM Table request ({len(unique_stations)} station locations vs {len(fires)} targets)...")

            response = self.http_session.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == "Ok":
                # Server returns a matrix (2D array) of travel times in seconds
                durations = data["durations"]

                # Decode the matrix and assign back to each resource in the system
                for i, station_loc in enumerate(unique_stations):
                    for j, fire in enumerate(fires):
                        duration_seconds = durations[i][j]

                        # Server returns None if no road exists (e.g., crossing sea/border)
                        if duration_seconds is not None:
                            eta_hours = duration_seconds / 3600.0  # Convert from seconds to hours
                        else:
                            eta_hours = 999.0  # Not accessible

                        # Update this time for all resources at that station
                        for res in stations_dict[station_loc]:
                            matrix[res.id][fire.id] = eta_hours

                print("   ⚡ OSRM Table API: Complete matrix returned successfully in a single call!")
                return matrix
            else:
                print(f"⚠️ Server Error: {data.get('code')}")

        except Exception as e:
            print(f"🔌 OSRM Table API Error (switching to mathematical fallback): {e}")

        # Fallback mechanism: if API failed, use quick mathematical calculation (offline)
        print("🔄 Computing matrix using local offline engine...")
        for res in resources:
            for fire in fires:
                dist_km = self._calculate_distance(res.current_lat, res.current_lon, fire.latitude, fire.longitude)
                eta_hours = (dist_km * 1.3) / 60.0
                matrix[res.id][fire.id] = eta_hours

        return matrix

    def step4_optimize_and_dispatch(self, unsolved_fires, math_survivors, eta_matrix, time_horizon_hours, fire_demands,
                                    allocated_in_this_cycle, available_supply, llm_summary, district_name):
        """Execute Mixed Integer Linear Programming (MILP) optimization to allocate resources to fires based on weighted cost function (SDI, resource power, travel time), then dispatch assigned resources and collect data for LLM summary generation."""
        print("     🧠 Activating global optimization engine (MILP) for arena...")
        prob = pulp.LpProblem("Fire_Resource_Allocation", pulp.LpMinimize)

        fire_ids = [f.id for f in unsolved_fires]
        res_ids = [r.id for r in math_survivors]

        fire_dict = {f.id: f for f in unsolved_fires}
        res_dict = {r.id: r for r in math_survivors}

        # Boolean variable for each combination of resource and fire
        assign_vars = pulp.LpVariable.dicts("Assign",
                                            ((r, f) for r in res_ids for f in fire_ids),
                                            cat='Binary')

        # Calculate three-layer cost function (Cost Matrix)
        costs = {}
        for r in res_ids:
            resource = res_dict[r]
            # Second layer: penalty for resource power (to preserve reserves)
            resource_power_penalty = self.BASE_PRODUCTION_RATES.get(resource.resource_type, 0.0)

            for f in fire_ids:
                eta_hours = eta_matrix[r][f]

                # Build weighted cost: SDI (10,000) > resource type > travel time
                base_penalty = 10000.0
                power_penalty = resource_power_penalty
                time_penalty = eta_hours * 100.0

                costs[r, f] = base_penalty + power_penalty + time_penalty

        # Define objective function
        # Engine will try to minimize total of these costs
        prob += pulp.lpSum(assign_vars[r, f] * costs[r, f] for r in res_ids for f in fire_ids), "Minimize_Total_Cost"

        # Constraint 1: each resource sent to maximum one fire
        for r in res_ids:
            prob += pulp.lpSum(assign_vars[r, f] for f in fire_ids) <= 1

        # Constraint 2: satisfy demand for each fire
        for f in fire_ids:
            current_fire = fire_dict[f]
            demand = fire_demands[f]  # Use updated remaining demand

            yield_sum = []
            for r in res_ids:
                eta_hours = eta_matrix[r][f]
                net_yield = self.get_net_yield(res_dict[r].resource_type, current_fire, eta_hours, time_horizon_hours)
                yield_sum.append(assign_vars[r, f] * net_yield)

            prob += pulp.lpSum(yield_sum) >= demand

        # Solve without internal console messages
        prob.solve(pulp.PULP_CBC_CMD(msg=False))

        if pulp.LpStatus[prob.status] == 'Optimal':
            print("     ✅ Found optimal global solution for arena (weighted cost-based)!")
            saar_counters = {f: 0 for f in fire_ids}

            # Initialize district in JSON dictionary
            if district_name not in llm_summary:
                llm_summary[district_name] = {}

            # Perform actual dispatch and collect data
            for r in res_ids:
                for f in fire_ids:
                    if pulp.value(assign_vars[r, f]) == 1.0:
                        selected_res = res_dict[r]
                        target_fire = fire_dict[f]

                        selected_res.status = 'EN_ROUTE'
                        selected_res.assigned_event_id = target_fire.id
                        allocated_in_this_cycle.add(selected_res.id)

                        actual_eta_mins = eta_matrix[r][f] * 60
                        print(
                            f"       🚒 Assigned {selected_res.resource_type} vehicle to fire {target_fire.id} (ETA: {actual_eta_mins:.1f} min)")

                        # Collect for JSON
                        fire_key = f"fire_{target_fire.id}"
                        if fire_key not in llm_summary[district_name]:
                            llm_summary[district_name][fire_key] = {
                                "status": "ACTIVELY_DISPATCHING",
                                "location": {
                                    "lat": target_fire.latitude,
                                    "lon": target_fire.longitude
                                },
                                "resources": []
                            }

                        llm_summary[district_name][fire_key]["resources"].append({
                            "type": selected_res.resource_type,
                            "eta_minutes": round(actual_eta_mins, 1),
                            "station": selected_res.station.name if selected_res.station else "Unknown"
                        })

                        # Enabler protocol: assign ESHED tanker for every 3 SAAR vehicles
                        if selected_res.resource_type == "SAAR":
                            saar_counters[f] += 1
                            if saar_counters[f] % 3 == 0:
                                allocated_eshed = self._allocate_enabler_eshed(target_fire,
                                                                               available_supply.get("ESHED", []),
                                                                               allocated_in_this_cycle)
                                if allocated_eshed:
                                    eshed_eta = self._get_driving_eta_minutes(
                                        allocated_eshed.current_lon, allocated_eshed.current_lat,
                                        target_fire.longitude, target_fire.latitude
                                    )
                                    llm_summary[district_name][fire_key]["resources"].append(
                                        {"type": "ESHED (Water Supply)", "eta_minutes": round(eshed_eta, 1),
                                         "station": allocated_eshed.station.name if allocated_eshed.station else "Unknown"})
            return True
        else:
            return False

    def step5_update_resource_locations(self):
        """Update the location of each dispatched resource to the fire location and change status to NOT_AVAILABLE to prevent reassignment in subsequent allocation rounds."""
        from app.models.resources import Resource
        from app.models.fire_events import FireEvent

        # Fetch all resources the algorithm just dispatched (EN_ROUTE status)
        dispatched_resources = Resource.query.filter_by(status='EN_ROUTE').all()

        if not dispatched_resources:
            print("   ℹ️ No vehicles found with EN_ROUTE status to update.")
            return

        print(f"\n📍 Updates: Updating locations of {len(dispatched_resources)} vehicles to event endpoints...")

        for res in dispatched_resources:
            if not res.assigned_event_id:
                continue

            # Fetch the event to which the resource was assigned
            target_fire = FireEvent.query.get(res.assigned_event_id)

            if target_fire:
                # Update location and status
                res.current_lat = target_fire.latitude
                res.current_lon = target_fire.longitude
                res.status = 'NOT_AVAILABLE'

                print(f"   ✅ Vehicle {res.id} ({res.resource_type}) arrived at fire {target_fire.id} and marked unavailable.")

        # Save to database
        try:
            db.session.commit()
            print("   💾 Location changes saved successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"   ❌ Error updating vehicle locations: {e}")

    def _generate_and_save_district_summaries(self, llm_summary_json):
        """Process summary JSON by sending it to LLM agent for structured formatting, save the results to database, and broadcast structured summaries to React frontend via WebSockets."""
        if not llm_summary_json:
            return

        import json
        import os
        from flask_socketio import SocketIO
        from app.extensions import db
        from app.models.commander_logs import CommandLog
        from app.agents.llm_agent import LLMAgent

        llm = LLMAgent()
        print("\n🗣️ Passing data to Spokesperson Agent (LLM Agent) for summary generation...")

        # Efficiency: set up emitter once outside loop
        redis_url = os.environ.get('REDIS_URL')
        emitter = SocketIO(message_queue=redis_url) if redis_url else SocketIO()

        for district, fires_data in llm_summary_json.items():
            try:
                # Get response from LLM
                raw_summary_string = llm.summarize_dispatch(district, fires_data)
                print(f"   ✅ Received raw LLM output for district {district}:\n      {raw_summary_string}\n")

                # Convert string to Python object (dictionary)
                try:
                    structured_data = json.loads(raw_summary_string)
                    # Extract recommendations array (or empty list if none)
                    fires_allocation = structured_data.get("fires_allocation", [])

                    for allocation in fires_allocation:
                        if not isinstance(allocation, dict):
                            print(f"      ⚠️ Skipping corrupted item in JSON for district {district}: {allocation}")
                            continue

                        event_id = allocation.get("event_id")
                        tactical_summary = allocation.get("tactical_summary")

                        if event_id and tactical_summary:
                            # Find specific fire and update its column
                            fire_event = FireEvent.query.get(event_id)
                            if fire_event:
                                fire_event.tactical_summary = tactical_summary

                    # Save all fire updates at once
                    db.session.commit()

                except json.JSONDecodeError as e:
                    print(f"❌ Error: LLM did not return valid JSON for {district}. Exception: {e}")
                    structured_data = {
                        "district_name": district,
                        "district_overview": "⚠️ Error formatting dispatch strategy.",
                        "fires_allocation": []
                    }

                # Save to database (save string as-is in operations log)
                new_log = CommandLog(
                    district_name=district,
                    raw_json=fires_data,
                    llm_summary_text=raw_summary_string
                )
                db.session.add(new_log)

                # Live broadcast to React - we broadcast the structured object
                print(f"📡 Broadcasting structured commander summary for district {district} via WebSockets...")
                emitter.emit('commander_update', structured_data)
                print("Emitted commander_update event to WebSocket clients.")

            except Exception as e:
                print(f"   ⚠️ Error creating LLM summary for district {district}: {e}")

        # Final commit of operations log
        try:
            db.session.commit()
            print("   💾 Operations log saved successfully to DB.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error saving operations log: {e}")

    def run_master_cycle(self):
        """Execute the main strategic command loop using Time-First Architecture to iteratively allocate resources to active fires across expanding time horizons until all demands are satisfied or time windows are exhausted."""
        from app.models.fire_events import FireEvent
        from app.models.resources import Station
        from app.extensions import db
        from app.agents.predict_agent import FirePredictorAgent

        print("\n==================================================")
        print("🚀 Starting strategic command cycle (Master Cycle)...")
        print("==================================================")

        cycle_start_time = time.time()

        master_llm_summary = {}

        # Setup and prepare arenas (outside loop)
        active_fires = FireEvent.query.filter(FireEvent.is_active == True).all()
        if not active_fires:
            print("✅ No active fires. Returning to routine.")
            print(f"⏱️ Master Cycle completed early (Early Return) in {time.time() - cycle_start_time:.2f} seconds.")
            return

        all_stations = Station.query.all()
        available_supply = self._fetch_available_resources()

        # Build arena dictionary by districts
        district_zones = {}
        for fire in active_fires:
            d_name = self._assign_district_to_fire(fire, all_stations)
            if d_name not in district_zones:
                district_zones[d_name] = []
            district_zones[d_name].append(fire)

        print(f"🗺️ System grouped {len(active_fires)} fires into {len(district_zones)} district arenas.")

        allocated_in_this_cycle = set()
        allocated_yield_per_fire = {fire.id: 0.0 for fire in active_fires}  # Track dispatch history
        fire_demands = {fire.id: 0.0 for fire in active_fires}

        predictor = FirePredictorAgent()
        time_horizons = [1.0, 2.0, 3.0, 6.0, 12.0]  # Time windows (in hours)

        # The main loop (Spatio-Temporal Loop)
        for target_hours in time_horizons:
            step_start_time = time.time()

            # Stop if everything is solved
            if all(fire.is_active == False for fire in active_fires):
                print("🎯 All arenas nationwide have received full response!")
                break

            print(f"\n⏳ Opening prediction time window for {target_hours} hours ahead...")

            # Prediction and re-demand for current time
            try:
                predictor.run_cycle(target_hours=target_hours)
                self.step1_calculate_demands()
            except Exception as e:
                print(f"⚠️ Error running prediction/demand: {e}")

            # Iterate over each arena for feasibility check
            for district_name, district_fires in district_zones.items():

                unsolved_fires = [f for f in district_fires if f.is_active]
                if not unsolved_fires:
                    continue  # This arena is solved

                print(f"  📍 Checking arena: {district_name} ({len(unsolved_fires)} active fires)")

                # Calculate net demand for the arena
                total_district_demand = 0.0
                for fire in unsolved_fires:
                    db.session.refresh(fire)  # Pull updated demand just calculated
                    updated_demand = getattr(fire, 'demand_perimeter_m', 0.0)

                    # Deduct production from forces already sent to this fire (to avoid double counting)
                    current_demand = updated_demand - allocated_yield_per_fire[fire.id]
                    fire_demands[fire.id] = max(0, current_demand)
                    total_district_demand += fire_demands[fire.id]

                if total_district_demand <= 0:
                    for f in unsolved_fires: f.is_active = False
                    continue

                # Phase A: Fast mathematical filter (who can reach the arena?)
                math_survivors = []
                for res_type, resources in available_supply.items():
                    if res_type == "ESHED": continue

                    for res in resources:
                        if res.id in allocated_in_this_cycle: continue

                        # District restriction in first hour
                        if target_hours <= 1.0 and res.station.district != district_name:
                            continue

                        # Can the vehicle reach at least one fire in the arena in time?
                        can_reach = False
                        for fire in unsolved_fires:
                            dist = self._calculate_distance(fire.latitude, fire.longitude, res.current_lat,
                                                            res.current_lon)
                            fast_eta = (dist * 1.4) / 60.0
                            if fast_eta < target_hours:
                                can_reach = True
                                break

                        if can_reach:
                            math_survivors.append(res)

                # Phase B: Get accurate times from API
                eta_matrix = self._get_eta_matrix(math_survivors, unsolved_fires)

                # Feasibility Check
                total_potential_yield = 0.0

                for res in math_survivors:
                    # To estimate potential, assume vehicle goes to fire it reaches fastest
                    best_fire = min(unsolved_fires, key=lambda f: eta_matrix[res.id][f.id])
                    best_eta = eta_matrix[res.id][best_fire.id]
                    net_time = target_hours - best_eta

                    if net_time > 0:
                        # Calculate hourly production
                        hourly_yield = self.get_actual_yield(res.resource_type, best_fire)
                        total_potential_yield += hourly_yield * net_time

                if total_potential_yield >= total_district_demand:
                    print(
                        f"     ✅ Feasibility found! (Supply: {total_potential_yield:.1f} | Demand: {total_district_demand:.1f})")
                    # Run step 4
                    optimization_success = self.step4_optimize_and_dispatch(
                        unsolved_fires=unsolved_fires,
                        math_survivors=math_survivors,
                        eta_matrix=eta_matrix,
                        time_horizon_hours=target_hours,
                        fire_demands=fire_demands,
                        allocated_in_this_cycle=allocated_in_this_cycle,
                        available_supply=available_supply,
                        llm_summary=master_llm_summary,
                        district_name=district_name
                    )

                    if optimization_success:
                        # Only if engine succeeded in dispatching, mark these fires as solved
                        for f in unsolved_fires:
                            f.is_active = False
                        print(f"     🎯 Arena {district_name} solved successfully and resources dispatched.")
                    else:
                        print(f"     ⚠️ Despite theoretical feasibility, engine found no valid allocation. Waiting for time window expansion.")
                else:
                    print(
                        f"     ❌ Insufficient capacity (missing {total_district_demand - total_potential_yield:.1f} meters). Waiting for time window expansion.")

            step_elapsed = time.time() - step_start_time
            print(f"   ⏱️ Window {target_hours}h completed in {step_elapsed:.2f} seconds.")

        # Write to database
        try:
            db.session.commit()
            print("💾 Command cycle completed. Dispatches saved successfully.")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Error saving dispatches: {e}")

        total_elapsed = time.time() - cycle_start_time
        print(f"\n⏱️ Master Cycle completed in {total_elapsed:.2f} seconds total.")

        # Generate spokesperson summaries (LLM) and save to log
        import json
        print("\n📝 Collected JSON Summary:")
        print(json.dumps(master_llm_summary, indent=2, ensure_ascii=False))

        self._generate_and_save_district_summaries(master_llm_summary)

        self.step5_update_resource_locations()

        return master_llm_summary

    def _get_driving_eta_minutes(self, start_lon, start_lat, dest_lon, dest_lat):
        """Calculate driving time (ETA) in minutes between two points using OSRM routing API with fallback to aerial distance calculation if the server is unavailable."""
        # Build URL according to OSRM standard (longitude then latitude)
        url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{dest_lon},{dest_lat}?overview=false"

        try:
            # Set hard timeout of 5 seconds. Emergency system cannot wait forever.
            response = self.http_session.get(url, timeout=5.0)

            # Throws exception if server returned error code like 404 or 500
            response.raise_for_status()

            data = response.json()

            # Verify request succeeded and there's a valid route in output
            if data.get("code") == "Ok" and len(data.get("routes", [])) > 0:
                # Travel time returned in seconds, divide by 60 to get minutes
                duration_seconds = data["routes"][0]["duration"]
                return duration_seconds / 60.0
            else:
                print(f"⚠️ OSRM API Warning: Received invalid response from server: {data.get('code')}")

        except requests.exceptions.RequestException as e:
            # Catch network issues, disconnections, timeouts, etc.
            print(f"🔌 Communication error with navigation server (OSRM): {e}")

        # Fallback mechanism (emergency backup)
        print("🔄 Activating backup mechanism for ETA calculation (based on radius and average speed)...")

        # Calculate aerial distance in kilometers (using our existing function)
        # Note that here the order is latitude then longitude
        distance_km = self._calculate_distance(start_lat, start_lon, dest_lat, dest_lon)

        # Assume average travel speed of 60 km/h (one kilometer per minute)
        # Multiply by factor of 1.3 to compensate for roads not being straight (Tortuosity factor)
        average_speed_kpm = 60.0 / 60.0  # kilometers per minute
        estimated_minutes = (distance_km / average_speed_kpm) * 1.3

        return estimated_minutes
