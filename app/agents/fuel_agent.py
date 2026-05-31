import json
import time

import requests

# Global session for improved performance in concurrent requests
esri_session = requests.Session()
ESRI_LULC_URL = "https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer/identify"

# Mapping of ESRI Sentinel-2 land cover pixel values to fuel types and their respective fuel load factors
FUEL_CLASSES = {
    "1": {"type": "Water", "fuel_load": 0.0},
    "2": {"type": "Trees", "fuel_load": 2.5},
    "4": {"type": "Flooded Vegetation", "fuel_load": 0.2},
    "5": {"type": "Crops", "fuel_load": 0.4},
    "7": {"type": "Built Area", "fuel_load": 0.0},
    "8": {"type": "Bare Ground", "fuel_load": 0.0},
    "9": {"type": "Snow/Ice", "fuel_load": 0.0},
    "10": {"type": "Clouds", "fuel_load": -1.0},
    "11": {"type": "Rangeland", "fuel_load": 0.4}
}


def enrich_with_fuel(fire_event):
    """
    Enriches a fire event with fuel type and fuel load data by querying the ESRI Sentinel-2 Land Cover API at the fire's coordinates.
    Takes a fire_event object with latitude and longitude, updates its fuel_type and fuel_load attributes based on land cover data, and returns nothing.
    """
    start_time = time.time()
    print(f"🌲 Fuel Agent: Working on Event #{fire_event.id}...")

    # Build valid geometry object - using GPS degrees
    geometry_obj = {
        "x": fire_event.longitude,
        "y": fire_event.latitude,
        "spatialReference": {"wkid": 4326}
    }

    # Parameters adapted for extracting point data without unnecessary geometry
    params = {
        "geometry": json.dumps(geometry_obj),
        "geometryType": "esriGeometryPoint",
        "returnGeometry": "false",
        "returnCatalogItems": "false",
        "f": "json"
    }

    max_retries = 2

    for attempt in range(1, max_retries + 1):
        try:
            # Using Session with short timeout
            response = esri_session.get(ESRI_LULC_URL, params=params, timeout=(2.0, 5.0))

            if response.status_code == 200:
                data = response.json()

                if "value" in data and data["value"] != "NoData":
                    pixel_value = data["value"]

                    # Retrieve full object from dictionary, with default value if not found
                    fuel_info = FUEL_CLASSES.get(str(pixel_value), {"type": "Unknown", "fuel_load": 0.0})

                    # Update fuel type and fuel load in the fire event
                    fire_event.fuel_type = fuel_info["type"]
                    fire_event.fuel_load = fuel_info["fuel_load"]

                    print(
                        f"✅ Fuel Updated: Event #{fire_event.id} is '{fire_event.fuel_type}' (Load: {fire_event.fuel_load})")
                    print(f"⏱️ Fuel Agent Time: {(time.time() - start_time):.1f} seconds")
                    return
                else:
                    print(f"⚠️ Fuel Agent: No data found for Event #{fire_event.id} coordinates.")
                    return
            else:
                print(f"🔄 Fuel Error: Server returned {response.status_code}. Retrying...")
                time.sleep(1)

        except requests.exceptions.Timeout:
            print(f"⚠️ Fuel Timeout (Attempt {attempt}).")
        except Exception as e:
            print(f"⚠️ Fuel Connection Error (Attempt {attempt}): {e}")

    print(f"❌ Fuel Failed after {max_retries} attempts for Event #{fire_event.id}.")
