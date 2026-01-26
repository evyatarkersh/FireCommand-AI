import requests
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

# כתובת ה-API של Overpass (השער לנתוני OpenStreetMap)
OVERPASS_URL = "http://overpass-api.de/api/interpreter"

def fetch_and_save_fuel_type(lat, lon, fire_event_id):
    """
    בודק מהו סוג הקרקע במיקום השריפה ושומר ב-DB.
    """
    print(f"🌲 Fuel Agent: בודק סוג קרקע לאירוע {fire_event_id} ({lat}, {lon})...")
    
    try:
        # 1. שאילתה ל-OSM: "מה נמצא ברדיוס 50 מטר סביב הנקודה?"
        # אנחנו מחפשים תגיות של טבע (natural) או שימוש קרקע (landuse)
        overpass_query = f"""
            [out:json];
            (
              node(around:50,{lat},{lon})["natural"];
              way(around:50,{lat},{lon})["natural"];
              relation(around:50,{lat},{lon})["natural"];
              node(around:50,{lat},{lon})["landuse"];
              way(around:50,{lat},{lon})["landuse"];
              relation(around:50,{lat},{lon})["landuse"];
            );
            out tags;
        """
        
        response = requests.get(OVERPASS_URL, params={'data': overpass_query})
        data = response.json()
        
        # 2. ניתוח התשובה (Parsing)
        fuel_type = "UNKNOWN"
        fuel_load = 0.5 # ברירת מחדל (צימחייה דלילה)

        if 'elements' in data and len(data['elements']) > 0:
            # לוקחים את האלמנט הראשון שמצאנו
            tags = data['elements'][0].get('tags', {})
            
            natural = tags.get('natural')
            landuse = tags.get('landuse')
            
            print(f"   🔍 OSM Tags found: natural={natural}, landuse={landuse}")
            
            # לוגיקת מיפוי: תרגום תגיות OSM לסוגי דלק
            if natural in ['wood', 'tree_row'] or landuse in ['forest']:
                fuel_type = "FOREST"
                fuel_load = 4.0 # עומס גבוה (יער)
                
            elif natural in ['scrub', 'heath', 'grassland'] or landuse in ['meadow', 'grass', 'farmland']:
                fuel_type = "SHRUB"
                fuel_load = 2.0 # עומס בינוני (שיחים/שדה)
                
            elif landuse in ['residential', 'industrial', 'commercial', 'retail']:
                fuel_type = "URBAN"
                fuel_load = 0.2 # עומס נמוך מאוד (בטון מאיט את האש)
                
            elif natural in ['sand', 'bare_rock', 'water']:
                fuel_type = "BARREN"
                fuel_load = 0.0 # לא דליק
                
        else:
            print("   ⚠️ לא נמצא מידע מדויק ב-OSM, משתמש בברירת מחדל.")
            # כאן אפשר להכניס את הגיבוי לפי קו רוחב אם רוצים
            if lat > 31.5: 
                fuel_type = "MIXED_VEGETATION"
                fuel_load = 2.5
            else:
                fuel_type = "DESERT"
                fuel_load = 0.5

        print(f"   🌲 סיווג סופי: {fuel_type} (Load Index: {fuel_load})")

        # 3. עדכון בסיס הנתונים
        _update_db(fire_event_id, fuel_type, fuel_load)

    except Exception as e:
        print(f"❌ Fuel Agent Error: {e}")

def _update_db(event_id, fuel_type, fuel_load):
    if not DB_URL: return
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            UPDATE fire_events 
            SET fuel_type = %s, fuel_load = %s
            WHERE id = %s
        """, (fuel_type, fuel_load, event_id))
        conn.commit()
        conn.close()
        print(f"✅ נתוני קרקע נשמרו בהצלחה.")
    except Exception as e:
        print(f"❌ DB Error: {e}")