import requests
import psycopg2
import os
import math
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
TOPO_API_URL = "https://api.opentopodata.org/v1/srtm30m"

def fetch_and_save_topography(lat, lon, fire_event_id):
    """מנתח שטח ומעדכן את רשומת השריפה בטבלה המאוחדת."""
    print(f"⛰️ Topo Agent: מנתח שטח לאירוע {fire_event_id}...")
    
    try:
        # 1. חישוב טופוגרפי
        offset = 0.0003 
        points = [f"{lat},{lon}", f"{lat+offset},{lon}", f"{lat-offset},{lon}", f"{lat},{lon+offset}", f"{lat},{lon-offset}"]
        
        response = requests.get(f"{TOPO_API_URL}?locations={'|'.join(points)}")
        data = response.json()
        
        if 'results' not in data: return

        elevations = [r['elevation'] for r in data['results']]
        z_center = elevations[0]
        
        # חישובים
        dz_dx = (elevations[3] - elevations[4]) / 60.0
        dz_dy = (elevations[1] - elevations[2]) / 60.0
        
        slope_deg = round(math.degrees(math.atan(math.sqrt(dz_dx**2 + dz_dy**2))), 1)
        
        aspect_deg = 0
        if dz_dx != 0:
            aspect_deg = math.degrees(math.atan2(dz_dy, -dz_dx))
            if aspect_deg < 0: aspect_deg += 90
            else: aspect_deg = 360 - aspect_deg + 90
            aspect_deg = round(aspect_deg % 360, 0)

        print(f"   📐 תוצאות: Elev={z_center}, Slope={slope_deg}, Aspect={aspect_deg}")

        # 2. עדכון הטבלה המאוחדת
        update_topo_record(fire_event_id, z_center, slope_deg, aspect_deg)

    except Exception as e:
        print(f"❌ Topo Error: {e}")

def ensure_topo_columns(cur):
    """בודק אם עמודות הטופוגרפיה קיימות ויוצר אותן אם לא."""
    columns = [
        ("topo_elevation", "FLOAT"),
        ("topo_slope", "FLOAT"),
        ("topo_aspect", "FLOAT")
    ]
    for col_name, col_type in columns:
        cur.execute(f"ALTER TABLE fire_events ADD COLUMN IF NOT EXISTS {col_name} {col_type};")

def update_topo_record(fire_id, elev, slope, aspect):
    if not DB_URL: return
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # --- תוספת: וידוא קיום עמודות ---
        ensure_topo_columns(cur)
        # -------------------------------

        # השאילתה המעודכנת
        cur.execute("""
            UPDATE fire_events 
            SET 
                topo_elevation = %s, 
                topo_slope = %s, 
                topo_aspect = %s
            WHERE id = %s
        """, (elev, slope, aspect, fire_id))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ נתוני Topo עודכנו ברשומה המאוחדת (ID: {fire_id})")
        
    except Exception as e:
        print(f"❌ DB Update Error: {e}")