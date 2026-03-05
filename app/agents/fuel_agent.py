import requests
import time

# --- שיפור 1: שימוש בשרת מראה (Mirror) מהיר יותר של Overpass ---
# השרת הזה בדרך כלל פחות עמוס מהשרת הגרמני הראשי
OVERPASS_URL = "https://lz4.overpass-api.de/api/interpreter" 
# אופציה חלופית אם עדיין איטי: "https://overpass.kumi.systems/api/interpreter"

# --- שיפור 2: Connection Pooling בדיוק כמו ב-IMS ---
osm_session = requests.Session()
osm_session.headers.update({
    "User-Agent": "FireCommand-AI-Agent/1.0 (Research Project)"
})

# זיכרון מטמון לאירועים סמוכים (חוסך 100% מהזמן לנקודות באותו קילומטר)
fuel_cache = {}

def enrich_with_fuel(fire_event):
    start_time = time.time()
    print(f"🌲 Fuel Agent: Working on Event #{fire_event.id}...")
    
    lat = fire_event.latitude
    lon = fire_event.longitude
    
    # מפתח לזיכרון (עיגול ל-2 ספרות, בערך קילומטר אחד)
    cache_key = (round(lat, 2), round(lon, 2))
    
    if cache_key in fuel_cache:
        cached_type, cached_load = fuel_cache[cache_key]
        fire_event.fuel_type = cached_type
        fire_event.fuel_load = cached_load
        print(f"⚡ Fuel Loaded from CACHE: {cached_type} ({(time.time() - start_time):.2f}s)")
        return

    try:
        overpass_query = f"""
            [out:json][timeout:5];
            (
              nwr(around:50,{lat},{lon})["natural"];
              nwr(around:50,{lat},{lon})["landuse"];
            );
            out tags;
        """
        
        # --- שיפור 3: טיימאאוט קצר + שימוש ב-Session ---
        # אנחנו נותנים לזה גג 2.5 שניות עכשיו
        response = osm_session.get(OVERPASS_URL, params={'data': overpass_query}, timeout=5)
        
        # ברירת מחדל בסיסית (אם ה-API ענה אבל אין שום מידע באזור הזה - שטח ריק)
        fuel_type = "UNKNOWN"
        fuel_load = 0.5

        if response.status_code == 200:
            data = response.json()
            if 'elements' in data and len(data['elements']) > 0:
                tags = data['elements'][0].get('tags', {})
                natural = tags.get('natural')
                landuse = tags.get('landuse')
                
                if natural in ['wood', 'tree_row'] or landuse == 'forest':
                    fuel_type = "FOREST"; fuel_load = 4.0
                elif natural in ['scrub', 'heath', 'grassland'] or landuse in ['meadow', 'grass', 'farmland']:
                    fuel_type = "SHRUB"; fuel_load = 2.0
                elif landuse in ['residential', 'industrial', 'commercial', 'retail']:
                    fuel_type = "URBAN"; fuel_load = 0.2
                elif natural in ['sand', 'bare_rock', 'water']:
                    fuel_type = "BARREN"; fuel_load = 0.0

        fire_event.fuel_type = fuel_type
        fire_event.fuel_load = fuel_load
        fuel_cache[cache_key] = (fuel_type, fuel_load)
        
        print(f"✅ Fuel Updated from OSM: {fuel_type} ({(time.time() - start_time):.2f}s)")

    except requests.exceptions.Timeout:
        # במקרה של טיימאאוט לא זורקים שגיאה, אלא משאירים UNKNOWN וממשיכים
        fire_event.fuel_type = "UNKNOWN"
        fire_event.fuel_load = 0.5
        print(f"⚠️ Fuel Agent Timeout (>2.5s). Marked as UNKNOWN.")
    except Exception as e:
        fire_event.fuel_type = "UNKNOWN"
        fire_event.fuel_load = 0.5
        print(f"⚠️ Fuel Agent Warning: {e}. Marked as UNKNOWN.")