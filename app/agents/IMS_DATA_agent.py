import requests
import os
import time
from dotenv import load_dotenv
from app.services.ims_stations_service import get_nearest_station

load_dotenv()
IMS_TOKEN = os.getenv("IMS_TOKEN")
IMS_BASE_URL = "https://api.ims.gov.il/v1/envista/stations"

# --- שיפור 1: יצירת Session גלובלי לכל התהליכונים (Connection Pooling) ---
ims_session = requests.Session()
# אנחנו מגדירים את ה-Headers פעם אחת בלבד על ה-Session
ims_session.headers.update({
    "Authorization": f"ApiToken {IMS_TOKEN}",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://ims.gov.il/"
})

def enrich_with_ims(fire_event):
    start_time = time.time()
    print(f"🕵️ IMS Agent: Working on Event #{fire_event.id}...")

    if not IMS_TOKEN:
        print("❌ IMS Agent Error: Token is missing.")
        return

    try:
        # 1. איתור תחנה קרובה
        lat = fire_event.latitude
        lon = fire_event.longitude
        
        station = get_nearest_station(lat, lon)
        if not station:
            print("⚠️ IMS Agent: No station found nearby.")
            return
            
        station_id = station['id']
        station_name = station['name']

        url = f"{IMS_BASE_URL}/{station_id}/data/latest"
        
        max_retries = 3
        
        for attempt in range(1, max_retries + 1):
            try:
                # --- שיפור 2: Timeout מפוצל (3 שניות חיבור, 10 שניות קריאה) ---
                # ושימוש ב-session במקום requests.get
                response = ims_session.get(url, timeout=(3.0, 10.0))
                
                if response.status_code != 200 or response.text.strip().startswith("<"):
                    print(f"   🔄 IMS Error (Attempt {attempt}/{max_retries}): Server blocked/failed. Retrying in 2s...")
                    time.sleep(0.5) # כאן הגיוני להשהות קצת לפני ניסיון חוזר
                    continue

                json_response = response.json()
                
                if "data" not in json_response or not json_response["data"]:
                    print(f"⚠️ IMS Empty Data: Station {station_name}")
                    return

                latest = json_response["data"][0]
                channels = latest.get("channels", [])

                # מילוי הנתונים
                fire_event.ims_station_id = station_id
                rain_val = 0.0
                
                # --- שיפור 3: מעבר מהיר על הנתונים עם Dictionary ---
                # הופכים את מערך הערוצים למילון { "TD": 25.0, "RH": 60 ... } לחיפוש מיידי
                channel_map = {ch.get("name"): ch.get("value") for ch in channels if ch.get("value") is not None}
                
                fire_event.ims_temp = channel_map.get("TD")
                fire_event.ims_humidity = channel_map.get("RH")
                fire_event.ims_wind_speed = channel_map.get("WS")
                fire_event.ims_wind_dir = int(channel_map["WD"]) if "WD" in channel_map else None
                fire_event.ims_rain = channel_map.get("Rain", 0.0)
                fire_event.ims_wind_gust = channel_map.get("WSmax")
                fire_event.ims_radiation = channel_map.get("Grad")

                print(f"✅ IMS Updated: {station_name} ({fire_event.ims_temp}°C)")
                print(f"⏱️ IMS Agent Time: {(time.time() - start_time):.1f} seconds")
                return 

            except requests.exceptions.Timeout:
                print(f"⚠️ IMS Timeout (Attempt {attempt}): Server took too long.")
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ IMS Connection Warning (Attempt {attempt}): {e}")
                time.sleep(1)

        print(f"❌ IMS Failed after {max_retries} attempts for {station_name}")

    except Exception as e:
        print(f"⏱️ IMS Agent Time (Failed): {(time.time() - start_time):.1f} seconds")
        print(f"❌ IMS General Error: {e}")