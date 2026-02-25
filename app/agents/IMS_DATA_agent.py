import requests
import os
from dotenv import load_dotenv
from app.services.ims_stations_service import get_nearest_station

load_dotenv()
IMS_TOKEN = os.getenv("IMS_TOKEN")
IMS_BASE_URL = "https://api.ims.gov.il/v1/envista/stations"

def enrich_with_ims(fire_event):
    """
    גרסה משופרת ועמידה יותר לשגיאות API
    """
    print(f"🕵️ IMS Agent: Working on Event #{fire_event.id}...")

    if not IMS_TOKEN:
        print("❌ IMS Agent Error: Token is missing.")
        return

    try:
        # 1. איתור תחנה
        lat = fire_event.latitude
        lon = fire_event.longitude
        
        station = get_nearest_station(lat, lon)
        if not station:
            print("⚠️ IMS Agent: No station found nearby.")
            return
            
        station_id = station['id']
        station_name = station['name'] # שומרים את השם להדפסה
        
        # 2. קריאה ל-API
        url = f"{IMS_BASE_URL}/{station_id}/data/latest"
        headers = {"Authorization": f"ApiToken {IMS_TOKEN}"}
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
        except requests.exceptions.Timeout:
            print(f"⚠️ IMS Timeout: Station {station_name} ({station_id}) took too long.")
            return
        except requests.exceptions.RequestException as e:
            print(f"⚠️ IMS Connection Error: {e}")
            return

        # 3. בדיקות תקינות לפני פענוח (התיקון החשוב!)
        if response.status_code == 204: # No Content
            print(f"⚠️ IMS Empty: Station {station_name} ({station_id}) has no data (204).")
            return
        
        if response.status_code != 200:
            print(f"⚠️ IMS Error: Station {station_name} ({station_id}) returned status {response.status_code}")
            return

        # בדיקה שהתוכן לא ריק
        if not response.content:
            print(f"⚠️ IMS Error: Station {station_name} ({station_id}) returned empty body.")
            return

        try:
            json_response = response.json()
        except ValueError:
            # כאן בדיוק קרתה השגיאה שלך קודם!
            print(f"⚠️ IMS Parsing Error: Station {station_name} ({station_id}) returned invalid JSON.")
            # הדפסה של התוכן הגולמי כדי שתבין מה חזר (אולי שגיאת HTML)
            print(f"   -> Raw response: {response.text[:100]}...") 
            return

        if "data" not in json_response or not json_response["data"]:
            print(f"⚠️ IMS Data Error: Station {station_name} ({station_id}) json has no 'data' field.")
            return

        latest = json_response["data"][0]
        channels = latest.get("channels", [])

        # 4. מיפוי הנתונים
        fire_event.ims_station_id = station_id
        
        # איפוס נתונים
        rain_val = 0.0
        
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

        print(f"✅ IMS Updated locally: Station={station_name}, Temp={fire_event.ims_temp}")

    except Exception as e:
        print(f"❌ IMS General Error: {e}")