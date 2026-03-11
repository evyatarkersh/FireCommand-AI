import requests
import json
import time

# Session גלובלי לשיפור ביצועים במקביליות
esri_session = requests.Session()
ESRI_LULC_URL = "https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer/identify"

# מילון מעודכן הכולל את סוג הקרקע והערכת עומס אש (Fuel Load)
FUEL_CLASSES = {
    "1": {"type": "Water", "fuel_load": 0.0},
    "2": {"type": "Trees", "fuel_load": 2.5},  # מטען אש כבד
    "4": {"type": "Flooded Vegetation", "fuel_load": 0.2},
    "5": {"type": "Crops", "fuel_load": 0.4},  # חקלאות
    "7": {"type": "Built Area", "fuel_load": 0.0},  # שטח בנוי
    "8": {"type": "Bare Ground", "fuel_load": 0.0},  # אדמה חשופה
    "9": {"type": "Snow/Ice", "fuel_load": 0.0},
    "10": {"type": "Clouds", "fuel_load": -1.0},  # חוסר נתונים עקב עננים
    "11": {"type": "Rangeland", "fuel_load": 0.4}  # שיחים ומרעה - אש מהירה
}


def enrich_with_fuel(fire_event):
    start_time = time.time()
    print(f"🌲 Fuel Agent: Working on Event #{fire_event.id}...")

    # בניית אובייקט הגיאומטריה התקין - שימוש במעלות GPS
    geometry_obj = {
        "x": fire_event.longitude,
        "y": fire_event.latitude,
        "spatialReference": {"wkid": 4326}
    }

    # פרמטרים מותאמים לשליפת נתון נקודתי ללא גיאומטריה מיותרת
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

                    # שליפת האובייקט המלא מהמילון, עם ערך ברירת מחדל אם לא נמצא
                    fuel_info = FUEL_CLASSES.get(str(pixel_value), {"type": "Unknown", "fuel_load": 0.0})

                    # עדכון סוג הדלק ועומס האש באירוע השריפה
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