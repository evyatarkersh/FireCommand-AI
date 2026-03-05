import requests
import time

# ה-API הרשמי של Esri למפת כיסוי קרקע עולמית (Land Cover) ברזולוציה 10 מטר
ESRI_LAND_COVER_URL = "https://tiledimageservices.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/Esri_2020_Land_Cover_V2/ImageServer/identify"

esri_session = requests.Session()
fuel_cache = {}

def enrich_with_fuel(fire_event):
    start_time = time.time()
    print(f"🌲 Fuel Agent: Working on Event #{fire_event.id}...")
    
    lat = fire_event.latitude
    lon = fire_event.longitude
    
    # זיכרון מטמון - עיגול ל-3 ספרות (רדיוס של בערך 100 מטר)
    # זה הרבה יותר מדויק מהקודם (שעשה רזולוציה של 1 ק"מ), כי הלוויין מאוד מדויק!
    cache_key = (round(lat, 3), round(lon, 3))
    
    if cache_key in fuel_cache:
        cached_type, cached_load = fuel_cache[cache_key]
        fire_event.fuel_type = cached_type
        fire_event.fuel_load = cached_load
        print(f"⚡ Fuel Loaded from CACHE: {cached_type} ({(time.time() - start_time):.2f}s)")
        return

    try:
        # פרמטרים לבקשת הפיקסל מהלוויין
        params = {
            "geometryType": "esriGeometryPoint",
            "geometry": f'{{"x":{lon},"y":{lat}}}',
            "spatialReference": '{"wkid":4326}', # קואורדינטות GPS רגילות
            "f": "json"
        }
        
        # טיימאאוט קצר מאוד - השרת הזה אמור לענות תוך עשיריות שנייה
        response = esri_session.get(ESRI_LAND_COVER_URL, params=params, timeout=2.0)
        
        fuel_type = "UNKNOWN"
        fuel_load = 0.5

        if response.status_code == 200:
            data = response.json()
            
            if "value" in data:
                # Esri מחזירה מספר שמייצג את סוג הקרקע
                pixel_value = data["value"]
                class_name = data.get("name", "Unknown")
                
                # תרגום הסיווג הלווייני למודל הדלק שלנו
                if pixel_value == '2':      # Trees
                    fuel_type = "FOREST"
                    fuel_load = 4.0
                elif pixel_value in ['4', '5', '11']: # Flooded Veg, Crops, Rangeland/Shrub
                    fuel_type = "SHRUB"
                    fuel_load = 2.0
                elif pixel_value == '7':    # Built Area (ערים/כבישים)
                    fuel_type = "URBAN"
                    fuel_load = 0.2
                elif pixel_value in ['1', '8', '9']: # Water, Bare Ground, Snow
                    fuel_type = "BARREN"
                    fuel_load = 0.0
                else:
                    fuel_type = "DESERT" if lat < 31.5 else "SHRUB"
                    fuel_load = 0.5
                    
                print(f"   🛰️ Satellite detected: {class_name} (Class {pixel_value})")
            else:
                print("   ⚠️ No pixel value found in satellite data.")

        fire_event.fuel_type = fuel_type
        fire_event.fuel_load = fuel_load
        fuel_cache[cache_key] = (fuel_type, fuel_load)
        
        print(f"✅ Fuel Updated (Satellite): {fuel_type} ({(time.time() - start_time):.2f}s)")

    except requests.exceptions.Timeout:
        fire_event.fuel_type = "UNKNOWN"
        fire_event.fuel_load = 0.5
        print(f"⚠️ Fuel Agent Timeout. Marked as UNKNOWN.")
    except Exception as e:
        fire_event.fuel_type = "UNKNOWN"
        fire_event.fuel_load = 0.5
        print(f"⚠️ Fuel Agent Error: {e}. Marked as UNKNOWN.")