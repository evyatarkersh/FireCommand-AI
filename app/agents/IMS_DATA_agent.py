import requests
import psycopg2
import os
from dotenv import load_dotenv
from app.services.ims_stations_service import get_nearest_station

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
IMS_TOKEN = os.getenv("IMS_TOKEN")
IMS_BASE_URL = "https://api.ims.gov.il/v1/envista/stations"

def fetch_weather_by_location(lat, lon, fire_event_id):
    """מקבל נ.צ. ו-ID, מוצא תחנה, מביא נתונים ומעדכן את רשומת השריפה."""
    print(f"🕵️ IMS Agent: מתחיל עבודה על אירוע {fire_event_id}...")

    # 1. איתור תחנה
    station = get_nearest_station(lat, lon)
    station_id = station['id']
    print(f"   📍 תחנה נבחרת: {station['name']} (ID: {station_id})")
    
    # 2. הבאת נתונים ושמירה
    fetch_and_update_db(station_id, fire_event_id)

def fetch_and_update_db(station_id, fire_event_id):
    if not IMS_TOKEN:
        print("❌ Error: טוקן חסר.")
        return

    url = f"{IMS_BASE_URL}/{station_id}/data/latest"
    headers = {"Authorization": f"ApiToken {IMS_TOKEN}"}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200: return

        json_response = response.json()
        if "data" not in json_response or not json_response["data"]: return

        latest = json_response["data"][0]
        
        # איסוף הנתונים
        data = {
            "temp": None, "humidity": None, "wind_speed": None, "wind_dir": None,
            "rain": 0.0, "wind_gust": None, "radiation": None
        }

        for channel in latest.get("channels", []):
            name = channel.get("name")
            val = channel.get("value")
            
            if name == "TD": data["temp"] = val
            elif name == "RH": data["humidity"] = val
            elif name == "WS": data["wind_speed"] = val
            elif name == "WD": data["wind_dir"] = val
            elif name == "Rain": data["rain"] = val
            elif name == "WSmax": data["wind_gust"] = val
            elif name == "Grad": data["radiation"] = val

        print(f"   🌤️ נתונים: Temp={data['temp']}, Wind={data['wind_speed']}, Gust={data['wind_gust']}")

        # 3. עדכון הטבלה המאוחדת
        update_fire_record(fire_event_id, station_id, data)

    except Exception as e:
        print(f"❌ IMS Error: {e}")

def ensure_ims_columns(cur):
    """בודק אם עמודות מזג האוויר קיימות ויוצר אותן אם לא."""
    columns = [
        ("ims_station_id", "INTEGER"),
        ("ims_temp", "FLOAT"),
        ("ims_humidity", "FLOAT"),
        ("ims_wind_speed", "FLOAT"),
        ("ims_wind_dir", "INTEGER"),
        ("ims_wind_gust", "FLOAT"),
        ("ims_rain", "FLOAT"),
        ("ims_radiation", "FLOAT")
    ]
    for col_name, col_type in columns:
        cur.execute(f"ALTER TABLE fire_events ADD COLUMN IF NOT EXISTS {col_name} {col_type};")

def update_fire_record(fire_id, station_id, data):
    if not DB_URL: return
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # --- תוספת: וידוא קיום עמודות ---
        ensure_ims_columns(cur)
        # -------------------------------
        
        # השאילתה המעודכנת
        cur.execute("""
            UPDATE fire_events
            SET 
                ims_station_id = %s,
                ims_temp = %s,
                ims_humidity = %s,
                ims_wind_speed = %s,
                ims_wind_dir = %s,
                ims_wind_gust = %s,
                ims_rain = %s,
                ims_radiation = %s
            WHERE id = %s
        """, (
            station_id, 
            data['temp'], data['humidity'], data['wind_speed'], data['wind_dir'], 
            data['wind_gust'], data['rain'], data['radiation'],
            fire_id
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ נתוני IMS עודכנו ברשומה המאוחדת (ID: {fire_id})")
        
    except Exception as e:
        print(f"❌ DB Update Error: {e}")