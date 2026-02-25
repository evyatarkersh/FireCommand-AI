import requests
import os
import time  # <--- הוספנו את ספריית הזמן להשהיות
from dotenv import load_dotenv
from app.services.ims_stations_service import get_nearest_station
# this is dumy pr
load_dotenv()
IMS_TOKEN = os.getenv("IMS_TOKEN")
IMS_BASE_URL = "https://api.ims.gov.il/v1/envista/stations"

def enrich_with_ims(fire_event):
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

        # 2. הכנת הבקשה עם "תחפושת" של דפדפן
        url = f"{IMS_BASE_URL}/{station_id}/data/latest"
        
        # אנחנו אומרים לשרת: "אנחנו לא סקריפט פייתון, אנחנו דפדפן כרום רגיל"
        headers = {
            "Authorization": f"ApiToken {IMS_TOKEN}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://ims.gov.il/"
        }
        
        # 3. מנגנון Retry חכם (ניסיון חוזר)
        max_retries = 3
        
        for attempt in range(1, max_retries + 1):
            try:
                # --- ההשהיה הקריטית ---
                # אנחנו מחכים 2 שניות לפני כל בקשה כדי לא להפעיל את ה"אזעקה" של השרת
                time.sleep(2) 
                
                # Timeout מוגדל ל-25 שניות לשרתים איטיים
                response = requests.get(url, headers=headers, timeout=25)
                
                # אם קיבלנו HTML (שגיאה) או סטטוס לא תקין
                if response.status_code != 200 or response.text.strip().startswith("<"):
                    print(f"   🔄 IMS Error (Attempt {attempt}/{max_retries}): Server blocked/failed. Retrying in 3s...")
                    time.sleep(3) # מחכים יותר זמן לפני הניסיון הבא
                    continue # מנסים שוב

                # אם הגענו לפה, קיבלנו JSON תקין!
                json_response = response.json()
                
                if "data" not in json_response or not json_response["data"]:
                    print(f"⚠️ IMS Empty Data: Station {station_name}")
                    return

                latest = json_response["data"][0]
                channels = latest.get("channels", [])

                # 4. מילוי הנתונים
                fire_event.ims_station_id = station_id
                
                # איפוס משתנים
                rain_val = 0.0 # ברירת מחדל לגשם
                
                for channel in channels:
                    name = channel.get("name")
                    val = channel.get("value")
                    
                    if val is not None:
                        if name == "TD": fire_event.ims_temp = val
                        elif name == "RH": fire_event.ims_humidity = val
                        elif name == "WS": fire_event.ims_wind_speed = val
                        elif name == "WD": fire_event.ims_wind_dir = int(val)
                        elif name == "Rain": rain_val = val
                        elif name == "WSmax": fire_event.ims_wind_gust = val
                        elif name == "Grad": fire_event.ims_radiation = val

                fire_event.ims_rain = rain_val

                print(f"✅ IMS Updated: {station_name} ({fire_event.ims_temp}°C)")
                return # יציאה מהפונקציה בהצלחה

            except Exception as e:
                print(f"⚠️ IMS Connection Warning (Attempt {attempt}): {e}")
                time.sleep(2)

        # אם יצאנו מהלולאה בלי להצליח
        print(f"❌ IMS Failed after {max_retries} attempts for {station_name}")

    except Exception as e:
        print(f"❌ IMS General Error: {e}")