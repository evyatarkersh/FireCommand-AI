import requests
import math
import time

# 1. יצירת Session גלובלי לשיפור ביצועים (לחיצת יד אחת לשרת)
topo_session = requests.Session()
topo_session.headers.update({"User-Agent": "FireCommand-Topo-Agent"})

# כתובת ה-API החיצוני
TOPO_API_URL = "https://api.opentopodata.org/v1/srtm30m"

def enrich_with_topography(fire_event):
    start_time = time.time()
    """
    מקבל אובייקט שריפה (FireEvent), פונה ל-API, ומעדכן את השדות באובייקט.
    הפונקציה עובדת בזיכרון (In-Memory) ולא מבצעת Commit ל-DB.
    """
    print(f"⛰️ Topo Agent: Working on Event #{fire_event.id}...")

    try:
        # שליפת הקואורדינטות מתוך האובייקט שכבר אצלנו ביד
        lat = fire_event.latitude
        lon = fire_event.longitude

        # הכנת הנקודות לחישוב
        offset = 0.0003 
        points = [
            f"{lat},{lon}", 
            f"{lat+offset},{lon}", 
            f"{lat-offset},{lon}", 
            f"{lat},{lon+offset}", 
            f"{lat},{lon-offset}"
        ]
        
        # הגדרת מספר ניסיונות מקסימלי במקרה של חסימת עומס (429)
        max_retries = 3
        
        for attempt in range(1, max_retries + 1):
            # 2. שימוש ב-Session במקום requests.get רגיל
            response = topo_session.get(f"{TOPO_API_URL}?locations={'|'.join(points)}", timeout=10)
            
            # 3. מנגנון ההגנה החכם (Exponential Backoff קלאסי)
            if response.status_code == 429:
                print(f"   ⚠️ Topo Rate Limit (429). Waiting 1s before retry {attempt}/{max_retries}...")
                time.sleep(0.5)
                continue # השרת ביקש לנשום? אנחנו מחכים שנייה ומנסים שוב בסיבוב הבא!
                
            if response.status_code != 200:
                print(f"⚠️ Topo API Error: Status {response.status_code}")
                break # שגיאה אחרת שאינה עומס (למשל 404 או 500) - יוצאים מהלולאה
                
            data = response.json()
            if 'results' not in data:
                print("⚠️ Topo API returned invalid JSON")
                break
                
            elevations = [r['elevation'] for r in data['results']]
            
            # בדיקה שלא קיבלנו None (קורה לפעמים בים או מחוץ למפה)
            if any(e is None for e in elevations):
                print("⚠️ Topo API returned None for elevation values")
                break

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

            # עדכון האובייקט בזיכרון
            fire_event.topo_elevation = z_center
            fire_event.topo_slope = slope_deg
            fire_event.topo_aspect = aspect_deg

            print(f"✅ Topo Updated locally: Elev={z_center}, Slope={slope_deg}")
            print(f"   ⏱️ Topo agent took {(time.time() - start_time):.2f} seconds")
            
            # סיימנו בהצלחה! יוצאים מהפונקציה כדי שלא ימשיך ללולאת הניסיונות
            return 

        # אם סיימנו את כל הלולאה ועדיין לא יצאנו דרך ה-return
        print(f"❌ Topo Agent failed after {max_retries} attempts.")
        print(f"   ⏱️ Topo agent time (Failed): {(time.time() - start_time):.2f} seconds")

    except Exception as e:
        print(f"❌ Topo Agent Failed (Exception): {e}")
        print(f"   ⏱️ Topo agent time (Failed): {(time.time() - start_time):.2f} seconds")

# אין כאן פונקציות ensure_columns או update_db - זה תפקיד המודל והמוניטור!