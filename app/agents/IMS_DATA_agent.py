"""
IMS Data Agent module for enriching fire events with real-time weather data from Israel Meteorological Service.
This agent finds the nearest weather station to a fire event and retrieves current meteorological conditions.
"""

import os
import time

import requests
from dotenv import load_dotenv

from app.services.ims_stations_service import get_nearest_station

load_dotenv()
IMS_TOKEN = os.getenv("IMS_TOKEN")
IMS_BASE_URL = "https://api.ims.gov.il/v1/envista/stations"

# Persistent session for IMS API requests with required authentication and headers
ims_session = requests.Session()
ims_session.headers.update({
    "Authorization": f"ApiToken {IMS_TOKEN}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://ims.gov.il/"
})


def enrich_with_ims(fire_event):
    """
    Enriches a fire event with real-time weather data from the nearest IMS weather station. Updates the fire_event object with temperature, humidity, wind speed/direction, rain, gusts, and radiation data retrieved from IMS API with retry logic.
    """
    start_time = time.time()
    print(f"🕵️ IMS Agent: Working on Event #{fire_event.id}...")

    # Validate IMS token is configured
    if not IMS_TOKEN:
        print("❌ IMS Agent Error: Token is missing.")
        return

    try:
        # Extract fire event coordinates
        lat = fire_event.latitude
        lon = fire_event.longitude

        # Find the closest weather station to the fire location
        station = get_nearest_station(lat, lon)
        if not station:
            print("⚠️ IMS Agent: No station found nearby.")
            return

        station_id = station['id']
        station_name = station['name']

        # Build API endpoint URL for the station's latest data
        url = f"{IMS_BASE_URL}/{station_id}/data/latest"

        max_retries = 3

        # Retry loop to handle transient API failures
        for attempt in range(1, max_retries + 1):
            try:
                response = ims_session.get(url, timeout=(3.0, 10.0))

                # Check if response is valid JSON (not HTML error page)
                if response.status_code != 200 or response.text.strip().startswith("<"):
                    print(f"   🔄 IMS Error (Attempt {attempt}/{max_retries}): Server blocked/failed. Retrying in 3s...")
                    time.sleep(0.5)
                    continue

                json_response = response.json()

                # Verify data structure contains expected fields
                if "data" not in json_response or not json_response["data"]:
                    print(f"⚠️ IMS Empty Data: Station {station_name}")
                    return

                latest = json_response["data"][0]
                channels = latest.get("channels", [])

                # Associate the station ID with this fire event
                fire_event.ims_station_id = station_id

                rain_val = 0.0

                # Parse weather channels and map to fire event attributes
                for channel in channels:
                    name = channel.get("name")
                    val = channel.get("value")

                    if val is not None:
                        if name == "TD":
                            fire_event.ims_temp = val
                        elif name == "RH":
                            fire_event.ims_humidity = val
                        elif name == "WS":
                            fire_event.ims_wind_speed = val
                        elif name == "WD":
                            fire_event.ims_wind_dir = int(val)
                        elif name == "Rain":
                            rain_val = val
                        elif name == "WSmax":
                            fire_event.ims_wind_gust = val
                        elif name == "Grad":
                            fire_event.ims_radiation = val

                # Assign rain value to fire event
                fire_event.ims_rain = rain_val

                print(f"✅ IMS Updated: {station_name} ({fire_event.ims_temp}°C)")
                total_time = time.time() - start_time
                print(f"⏱️ IMS Agent Time: {total_time:.1f} seconds")
                return

            except Exception as e:
                print(f"⚠️ IMS Connection Warning (Attempt {attempt}): {e}")
                time.sleep(0.5)

        print(f"❌ IMS Failed after {max_retries} attempts for {station_name}")

    except Exception as e:
        total_time = time.time() - start_time
        print("⏱️ IMS Agent Time (Failed): {:.1f} seconds".format(total_time))
        print(f"❌ IMS General Error: {e}")
