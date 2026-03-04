import requests
import time

# כתובת ה-API של Overpass (השער לנתוני OpenStreetMap)
OVERPASS_URL = "http://overpass-api.de/api/interpreter"

def enrich_with_fuel(fire_event):
    start_time = time.time()
    """
    מקבל אובייקט שריפה (FireEvent), פונה ל-OSM, ומעדכן את סוג הדלק באובייקט.
    הפונקציה עובדת בזיכרון (In-Memory) ולא מבצעת Commit ל-DB.
    """
    print(f"🌲 Fuel Agent: Working on Event #{fire_event.id}...")
    
    try:
        # 1. שליפת הקואורדינטות מתוך האובייקט
        lat = fire_event.latitude
        lon = fire_event.longitude
        
        # 2. שאילתה ל-OSM (הלוגיקה המקורית שלך)
        overpass_query = f"""
            [out:json][timeout:15];
            (
              nwr(around:50,{lat},{lon})["natural"];
              nwr(around:50,{lat},{lon})["landuse"];
            );
            out tags;
        """
        
        # הוספת Timeout היא קריטית ב-Overpass כי הוא שרת איטי לפעמים
        response = requests.get(OVERPASS_URL, params={'data': overpass_query}, timeout=15)
        
        # ערכי ברירת מחדל (למקרה שלא נמצא כלום)
        fuel_type = "UNKNOWN"
        fuel_load = 0.5

        # לוגיקת גיבוי לפי קו רוחב (אם ה-API נכשל או לא מחזיר תוצאות)
        if lat > 31.5: 
            fuel_type = "MIXED_VEGETATION"
            fuel_load = 2.5
        else:
            fuel_type = "DESERT"
            fuel_load = 0.5

        # ניתוח התשובה אם היא תקינה
        if response.status_code == 200:
            data = response.json()
            
            if 'elements' in data and len(data['elements']) > 0:
                # לוקחים את האלמנט הראשון שמצאנו
                tags = data['elements'][0].get('tags', {})
                natural = tags.get('natural')
                landuse = tags.get('landuse')
                
                print(f"   🔍 OSM Tags: natural={natural}, landuse={landuse}")
                
                # מיפוי תגיות לסוגי דלק
                if natural in ['wood', 'tree_row'] or landuse == 'forest':
                    fuel_type = "FOREST"
                    fuel_load = 4.0
                elif natural in ['scrub', 'heath', 'grassland'] or landuse in ['meadow', 'grass', 'farmland']:
                    fuel_type = "SHRUB"
                    fuel_load = 2.0
                elif landuse in ['residential', 'industrial', 'commercial', 'retail']:
                    fuel_type = "URBAN"
                    fuel_load = 0.2
                elif natural in ['sand', 'bare_rock', 'water']:
                    fuel_type = "BARREN"
                    fuel_load = 0.0

        # 3. עדכון האובייקט בזיכרון (החלק החשוב!)
        fire_event.fuel_type = fuel_type
        fire_event.fuel_load = fuel_load

        print(f"✅ Fuel Updated locally: {fuel_type} (Load: {fuel_load})")
        total_time = time.time() - start_time
        print("⏱️ Fuel Agent Time: {:.2f} seconds".format(total_time))

    except Exception as e:
        total_time = time.time() - start_time
        print("⏱️ Fuel Agent Time (Failed): {:.2f} seconds".format(total_time))
        # תופסים שגיאות (כמו Timeout או בעיית רשת) וממשיכים הלאה
        print(f"⚠️ Fuel Agent Failed (Skipping): {e}")
        # לא זורקים שגיאה החוצה, כדי ששאר הסוכנים ימשיכו לעבוד