import math
import time

import requests

# Create global session for improved performance with single handshake to the server
topo_session = requests.Session()
topo_session.headers.update({"User-Agent": "FireCommand-Topo-Agent"})

# External API URL for topography data
TOPO_API_URL = "https://api.opentopodata.org/v1/srtm30m"


def enrich_with_topography(fire_event):
    """
    Enriches a fire event object with topographic data including elevation, slope, and aspect by querying the OpenTopoData API. The function updates the fire_event object in-memory without committing to the database, and implements retry logic with exponential backoff for rate-limited requests.
    """
    start_time = time.time()
    print(f"⛰️ Topo Agent: Working on Event #{fire_event.id}...")

    try:
        # Extract coordinates from the fire event object
        lat = fire_event.latitude
        lon = fire_event.longitude

        # Prepare center point and four surrounding points for slope and aspect calculation
        offset = 0.0003
        points = [
            f"{lat},{lon}",
            f"{lat + offset},{lon}",
            f"{lat - offset},{lon}",
            f"{lat},{lon + offset}",
            f"{lat},{lon - offset}"
        ]

        # Set maximum number of retry attempts in case of rate limit
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            # Use persistent session for better performance
            response = topo_session.get(f"{TOPO_API_URL}?locations={'|'.join(points)}", timeout=10)

            # Handle rate limiting with exponential backoff strategy
            if response.status_code == 429:
                print(f"   ⚠️ Topo Rate Limit (429). Waiting 1s before retry {attempt}/{max_retries}...")
                time.sleep(0.5)
                continue

            if response.status_code != 200:
                print(f"⚠️ Topo API Error: Status {response.status_code}")
                break

            data = response.json()
            if 'results' not in data:
                print("⚠️ Topo API returned invalid JSON")
                break

            elevations = [r['elevation'] for r in data['results']]

            # Validate that all elevation values are present (can be None for sea or unmapped areas)
            if any(e is None for e in elevations):
                print("⚠️ Topo API returned None for elevation values")
                break

            z_center = elevations[0]

            # Calculate slope using elevation gradients in x and y directions
            dz_dx = (elevations[3] - elevations[4]) / 60.0
            dz_dy = (elevations[1] - elevations[2]) / 60.0
            slope_deg = round(math.degrees(math.atan(math.sqrt(dz_dx ** 2 + dz_dy ** 2))), 1)

            # Calculate aspect (direction of slope) in degrees from north
            aspect_deg = 0
            if dz_dx != 0:
                aspect_deg = math.degrees(math.atan2(dz_dy, -dz_dx))
                if aspect_deg < 0:
                    aspect_deg += 90
                else:
                    aspect_deg = 360 - aspect_deg + 90
                aspect_deg = round(aspect_deg % 360, 0)

            # Update the fire event object in memory
            fire_event.topo_elevation = z_center
            fire_event.topo_slope = slope_deg
            fire_event.topo_aspect = aspect_deg

            print(f"✅ Topo Updated locally: Elev={z_center}, Slope={slope_deg}")
            print(f"   ⏱️ Topo agent took {(time.time() - start_time):.2f} seconds")

            # Successfully enriched, exit the function
            return

        # Reached maximum retry attempts without success
        print(f"❌ Topo Agent failed after {max_retries} attempts.")
        print(f"   ⏱️ Topo agent time (Failed): {(time.time() - start_time):.2f} seconds")

    except Exception as e:
        print(f"❌ Topo Agent Failed (Exception): {e}")
        print(f"   ⏱️ Topo agent time (Failed): {(time.time() - start_time):.2f} seconds")

