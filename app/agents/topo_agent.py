import requests
import math

# כתובת ה-API החיצוני
TOPO_API_URL = "https://api.opentopodata.org/v1/srtm30m"

def enrich_with_topography(fire_event):
    """
    מקבל אובייקט שריפה (FireEvent), פונה ל-API, ומעדכן את השדות באובייקט.
    הפונקציה עובדת בזיכרון (In-Memory) ולא מבצעת Commit ל-DB.
    """
    print(f"⛰️ Topo Agent: Working on Event #{fire_event.id}...")

    try:
        # 1. שליפת הקואורדינטות מתוך האובייקט שכבר אצלנו ביד
        lat = fire_event.latitude
        lon = fire_event.longitude

        # 2. הכנת הנקודות לחישוב (הלוגיקה המתמטית שלך נשארה זהה)
        offset = 0.0003 
        points = [
            f"{lat},{lon}", 
            f"{lat+offset},{lon}", 
            f"{lat-offset},{lon}", 
            f"{lat},{lon+offset}", 
            f"{lat},{lon-offset}"
        ]
        
        # פנייה ל-API עם Timeout (כדי לא לתקוע את המערכת)
        response = requests.get(f"{TOPO_API_URL}?locations={'|'.join(points)}", timeout=10)
        
        if response.status_code != 200:
            print(f"⚠️ Topo API Error: Status {response.status_code}")
            return

        data = response.json()
        if 'results' not in data:
            print("⚠️ Topo API returned invalid JSON")
            return

        elevations = [r['elevation'] for r in data['results']]
        
        # בדיקה שלא קיבלנו None (קורה לפעמים בים או מחוץ למפה)
        if any(e is None for e in elevations):
            print("⚠️ Topo API returned None for elevation values")
            return

        z_center = elevations[0]
        
        # חישוב שיפוע (Slope)
        dz_dx = (elevations[3] - elevations[4]) / 60.0
        dz_dy = (elevations[1] - elevations[2]) / 60.0
        slope_deg = round(math.degrees(math.atan(math.sqrt(dz_dx**2 + dz_dy**2))), 1)
        
        # חישוב מפנה (Aspect)
        aspect_deg = 0
        if dz_dx != 0:
            aspect_deg = math.degrees(math.atan2(dz_dy, -dz_dx))
            if aspect_deg < 0: aspect_deg += 90
            else: aspect_deg = 360 - aspect_deg + 90
            aspect_deg = round(aspect_deg % 360, 0)

        # 3. עדכון האובייקט (החלק החשוב!)
        # אנחנו לא עושים SQL UPDATE, אלא משנים את התכונות של האובייקט בזיכרון
        fire_event.topo_elevation = z_center
        fire_event.topo_slope = slope_deg
        fire_event.topo_aspect = aspect_deg

        print(f"✅ Topo Updated locally: Elev={z_center}, Slope={slope_deg}")

    except Exception as e:
        # אנחנו תופסים את השגיאה, מדפיסים אותה, וממשיכים הלאה.
        # זה מבטיח שהמוניטור לא יקרוס גם אם ה-API של הטופוגרפיה למטה.
        print(f"❌ Topo Agent Failed (Skipping): {e}")

# אין כאן פונקציות ensure_columns או update_db - זה תפקיד המודל והמוניטור!