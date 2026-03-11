import requests
import json
import time

# Session גלובלי לשיפור ביצועים במקביליות
esri_session = requests.Session()
ESRI_LULC_URL = "https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer/identify"

FUEL_CLASSES = {
    "1": "Water",  # מים
    "2": "Trees",  # עצים
    "4": "Flooded Vegetation",  # צמחייה מוצפת
    "5": "Crops",  # חקלאות
    "7": "Built Area",  # שטח בנוי
    "8": "Bare Ground",  # אדמה חשופה
    "9": "Snow/Ice",  # שלג/קרח
    "10": "Clouds",  # עננים
    "11": "Rangeland"  # מרעה / שיחים
}


def enrich_with_fuel(fire_event):
    start_time = time.time()
    print(f"🌲 Fuel Agent: Working on Event #{fire_event.id}...")

    # בניית אובייקט הגיאומטריה התקין
    geometry_obj = {
        "x": fire_event.longitude,
        "y": fire_event.latitude,
        "spatialReference": {"wkid": 4326}
    }

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
            # שימוש ב-Session ו-Timeout קצר
            response = esri_session.get(ESRI_LULC_URL, params=params, timeout=(2.0, 5.0))

            if response.status_code == 200:
                data = response.json()

                if "value" in data and data["value"] != "NoData":
                    pixel_value = data["value"]
                    # ממירים למחרוזת למקרה שה-API החזיר מספר שלם במקום מחרוזת
                    fuel_type = FUEL_CLASSES.get(str(pixel_value), "Unknown")

                    # עדכון סוג הדלק באירוע השריפה
                    fire_event.fuel_type = fuel_type

                    print(f"✅ Fuel Updated: Event #{fire_event.id} is on '{fuel_type}'")
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