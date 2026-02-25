import requests
import os
from dotenv import load_dotenv
# אני מניח שהקובץ הזה קיים אצלך ועובד, כי הוא רק עושה חישוב מתמטי/גיאוגרפי
from app.services.ims_stations_service import get_nearest_station

load_dotenv()
IMS_TOKEN = os.getenv("IMS_TOKEN")
IMS_BASE_URL = "https://api.ims.gov.il/v1/envista/stations"

def enrich_with_ims(fire_event):
    """
    מקבל אובייקט שריפה (FireEvent).
    1. מוצא את התחנה המטאורולוגית הקרובה ביותר.
    2. מושך נתונים מה-API של השירות המטאורולוגי.
    3. מעדכן את האובייקט בזיכרון (ללא Commit).
    """
    print(f"🕵️ IMS Agent: Working on Event #{fire_event.id}...")

    if not IMS_TOKEN:
        print("❌ IMS Agent Error: Token is missing.")
        return

    try:
        # 1. שליפת מיקום מהאובייקט
        lat = fire_event.latitude
        lon = fire_event.longitude

        # 2. איתור תחנה קרובה (לוגיקה חיצונית קיימת)
        station = get_nearest_station(lat, lon)
        if not station:
            print("⚠️ IMS Agent: No station found nearby.")
            return
            
        station_id = station['id']
        print(f"   📍 Nearest Station: {station['name']} (ID: {station_id})")

        # 3. קריאה ל-API
        url = f"{IMS_BASE_URL}/{station_id}/data/latest"
        headers = {"Authorization": f"ApiToken {IMS_TOKEN}"}
        
        # Timeout של 10 שניות כדי לא לתקוע את המוניטור
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"⚠️ IMS API Error: Status {response.status_code}")
            return

        json_response = response.json()
        if "data" not in json_response or not json_response["data"]:
            print("⚠️ IMS API returned empty data.")
            return

        latest = json_response["data"][0]
        channels = latest.get("channels", [])

        # 4. מיפוי הנתונים (Parsing) - עדכון ישיר לאובייקט
        # שים לב: אנחנו מאפסים את הנתונים באובייקט לפני המילוי
        fire_event.ims_station_id = station_id
        
        # משתנים זמניים למילוי (כדי לשמור על הלוגיקה המקורית)
        # Rain מקבל 0.0 כברירת מחדל, השאר None
        rain_val = 0.0
        
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
                    fire_event.ims_wind_dir = int(val) # המרה ל-int לכיוון
                elif name == "Rain":
                    rain_val = val
                elif name == "WSmax":
                    fire_event.ims_wind_gust = val
                elif name == "Grad":
                    fire_event.ims_radiation = val

        # עדכון הגשם (בנפרד כי יש לו ברירת מחדל 0)
        fire_event.ims_rain = rain_val

        print(f"✅ IMS Updated locally: Temp={fire_event.ims_temp}, Wind={fire_event.ims_wind_speed}")

    except Exception as e:
        # תופסים שגיאות רשת/קוד כדי לא להפיל את המוניטור
        print(f"⚠️ IMS Agent Failed (Skipping): {e}")

# אין צורך בפונקציות ensure_columns או update_db SQL ידני