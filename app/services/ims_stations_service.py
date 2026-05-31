import csv
import math
import os

CSV_PATH = "stations.csv"
stations_cache = []


def load_stations():
    """
    Loads weather stations from the CSV file (StationId, StationName, Lat, Lon) into a global cache.
    Uses cached data on subsequent calls to avoid reloading. Returns None and populates stations_cache with dictionaries containing id, name, lat, and lon.
    """
    global stations_cache
    if stations_cache: return

    if not os.path.exists(CSV_PATH):
        print(f"⚠️ Warning: {CSV_PATH} not found. Using default station (Bet Dagan).")
        return

    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)

        # Skip the header row
        headers = next(reader, None)

        for row in reader:
            # Validate that row contains all 4 required columns
            if len(row) < 4: continue

            try:
                # Parse CSV structure: StationId, StationName, Lat, Lon
                s_id = int(row[0])
                name = row[1]
                lat = float(row[2])
                lon = float(row[3])

                stations_cache.append({
                    "id": s_id,
                    "name": name,
                    "lat": lat,
                    "lon": lon
                })
            except ValueError:
                continue

    print(f"✅ Loaded {len(stations_cache)} stations from CSV.")


def get_nearest_station(lat, lon):
    """
    Finds the nearest weather station to given coordinates using Euclidean distance.
    Takes latitude and longitude as inputs and returns a dictionary with the closest station's id, name, lat, and lon.
    """
    load_stations()

    # Return default Bet Dagan station if no stations are available
    if not stations_cache:
        return {"id": 24, "name": "Bet Dagan Default", "lat": 32.0, "lon": 34.8}

    nearest = None
    min_dist = float('inf')

    for station in stations_cache:
        # Calculate Euclidean distance between fire location and station
        dist = math.sqrt((station['lat'] - lat) ** 2 + (station['lon'] - lon) ** 2)

        if dist < min_dist:
            min_dist = dist
            nearest = station

    return nearest
