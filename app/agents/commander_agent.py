import math
import time
import requests

from shapely.geometry import shape
from pyproj import Geod
from app.extensions import db
from app.models.fire_events import FireEvent

class CommanderAgent:
    """
    סוכן המפקד: מבצע אופטימיזציית משאבים מבוססת תפוקת קו הגנה (Production Rate)
    ומדד קושי דיכוי מבצעי (SDI). כולל לולאת זמן-מרחב גלובלית.
    """

    # תפוקת מעבדה בסיסית (מטרים של קו הגנה בשעה)
    BASE_PRODUCTION_RATES = {
        "ROTEM": 800.0,  # תקיפה בתנועה (Pump-and-Roll)
        "SAAR": 300.0,  # פריסת זרנוקים איטית בשטח
        "AIR_TRACTOR": 2000.0,  # הטלה אווירית מהירה
        "ESHED": 0.0  # מאפשר (Enabler) - לא בונה קו אש בעצמו
    }

    @staticmethod
    def _calculate_distance(lat1, lon1, lat2, lon2):
        """ חישוב מרחק אווירי (בקילומטרים) בין שתי קואורדינטות (Haversine) """
        R = 6371.0  # רדיוס כדור הארץ בק"מ
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(
            dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def __init__(self):
        # הגדרת אובייקט מתמטי לחישוב מרחקים על פני כדור הארץ במטרים (WGS84)
        self.geod = Geod(ellps="WGS84")
        self.http_session = requests.Session()

    # ==========================================
    # שלב 1: חישוב דרישות (היקף פוליגון)
    # ==========================================

    def step1_calculate_demands(self):
        """
        עובר על כל האירועים הפעילים שיש להם פוליגון חיזוי,
        מחשב את היקף הפוליגון במטרים (הדרישה), ושומר בחזרה ל-DB.
        """
        print("\n👨‍✈️ Commander Agent (Step 1): סורק פוליגונים ומחשב דרישות קו הגנה...")

        active_events = FireEvent.query.filter(
            FireEvent.is_active == True,
            FireEvent.prediction_polygon.isnot(None)
        ).all()

        if not active_events:
            print("   💤 אין אירועים פעילים עם תחזית לחישוב דרישה כרגע.")
            return

        events_updated = 0
        for event in active_events:
            try:
                # חילוץ הגיאומטריה (הקואורדינטות) מתוך הפוליגון
                polygon_geom = shape(event.prediction_polygon)

                # חישוב ההיקף האמיתי במטרים
                perimeter_meters = self.geod.geometry_length(polygon_geom)

                # שמירת "תג המחיר" לאירוע ב-DB
                event.demand_perimeter_m = round(perimeter_meters, 1)
                events_updated += 1

                print(f"   🎯 אירוע {event.id}: דרישה הוגדרה ל-{event.demand_perimeter_m} מטרים.")

            except Exception as e:
                print(f"   ⚠️ שגיאה בחישוב דרישה לאירוע {event.id}: {e}")

        # שמירה מרוכזת ל-DB
        if events_updated > 0:
            try:
                db.session.commit()
                print("   💾 Commander: כל דרישות ההיקף נשמרו ב-DB בהצלחה!")
            except Exception as e:
                db.session.rollback()
                print(f"   ❌ Commander Error (Commit Fail): {e}")


    # ==========================================
    # שלב 2: חישוב היצע וכשירות משאבים (SDI)
    # ==========================================

    def _determine_terrain(self, fuel_type):
        """ מזהה האם מדובר בשטח עירוני או פתוח (יער) """
        if fuel_type in ["Built Area"]:
            return "URBAN"
        return "FOREST"

    def _calculate_sdi_factor(self, resource_type, terrain, slope):
        """
        מטריצת העבירות (SDI).
        מחזירה פקטור בין 0.0 ל-1.0 שקובע כמה הכלי יעיל בתנאים הנוכחיים.
        """
        is_steep = slope > 15.0

        if terrain == "FOREST":
            if is_steep:
                matrix = {"ROTEM": 0.7, "SAAR": 0.0, "AIR_TRACTOR": 0.9, "ESHED": 0.0}
            else:
                matrix = {"ROTEM": 1.0, "SAAR": 0.4, "AIR_TRACTOR": 1.0, "ESHED": 0.5}
        elif terrain == "URBAN":
            matrix = {"ROTEM": 0.5, "SAAR": 1.0, "AIR_TRACTOR": 0.0, "ESHED": 1.0}
        else:
            # Fallback
            matrix = {"ROTEM": 1.0, "SAAR": 1.0, "AIR_TRACTOR": 1.0, "ESHED": 1.0}

        return matrix.get(resource_type, 0.0)

    def get_actual_yield(self, resource_type, event):
        """
        מחשב את התפוקה האמיתית של רכב ספציפי באירוע ספציפי (מטרים/שעה).
        """
        terrain = self._determine_terrain(event.fuel_type)
        # תוקן לשימוש בשדה הנכון מה-DB
        slope = 0.0 if event.topo_slope is None else event.topo_slope

        base_rate = self.BASE_PRODUCTION_RATES.get(resource_type, 0.0)
        sdi_factor = self._calculate_sdi_factor(resource_type, terrain, slope)

        return base_rate * sdi_factor

    def _fetch_available_resources(self):
        """
        שולף את כל המשאבים הפנויים ממסד הנתונים פעם אחת בלבד ומסדר אותם לפי סוג.
        משתמש ב-joinedload כדי למשוך את נתוני התחנות מראש (Eager Loading) ולמנוע בעיית N+1.
        """
        from app.models.resources import Resource
        from sqlalchemy.orm import joinedload  # הייבוא הקריטי שמוסיף לנו את היכולת הזו

        # מוסיפים את options(joinedload...) כדי להגיד למסד הנתונים: "תביא גם את התחנה באותה נסיעה"
        available_resources = Resource.query.options(
            joinedload(Resource.station)
        ).filter_by(status='AVAILABLE').all()

        supply = {"SAAR": [], "ESHED": [], "ROTEM": [], "AIR_TRACTOR": []}
        for res in available_resources:
            if res.resource_type in supply:
                supply[res.resource_type].append(res)

        return supply

    def _allocate_enabler_eshed(self, fire, available_esheds, allocated_set):
        """
        לוגיקת ה-Enabler: מוצא את מכלית ה'אשד' הפנויה הקרובה ביותר ומשבץ אותה
        כדי לספק מים לרכבי ה'סער'.
        """
        closest_eshed = None
        min_dist = float('inf')

        # מחפש את האשד הקרוב ביותר בארץ שעוד לא גויס
        for eshed in available_esheds:
            if eshed.id in allocated_set or eshed.status != 'AVAILABLE':
                continue
            dist = self._calculate_distance(fire.latitude, fire.longitude, eshed.current_lat, eshed.current_lon)
            if dist < min_dist:
                min_dist = dist
                closest_eshed = eshed

        # אם מצאנו אשד, נשבץ אותו
        if closest_eshed:
            closest_eshed.status = 'EN_ROUTE'
            closest_eshed.assigned_event_id = fire.id
            allocated_set.add(closest_eshed.id)
            print(f"💧 [Enabler] שובץ רכב ESHED (אשד) ממרחק {min_dist:.1f} ק\"מ לתמיכה בשריפה {fire.id}.")
            return True
        else:
            print(f"⚠️ אזהרה קריטית: לא נותרו רכבי ESHED פנויים בארץ לתמיכה בשריפה {fire.id}!")
            return False

    def _assign_district_to_fire(self, fire, all_stations):
        """
        מוצא את התחנה הקרובה ביותר לשריפה ומשייך את השריפה למחוז של אותה תחנה.
        """
        closest_station = None
        min_dist = float('inf')
        
        for station in all_stations:
            dist = self._calculate_distance(fire.latitude, fire.longitude, station.latitude, station.longitude)
            if dist < min_dist:
                min_dist = dist
                closest_station = station
        
        # מחזיר את שם המחוז, או ערך ברירת מחדל אם משהו השתבש
        return closest_station.district if closest_station else "UNKNOWN"

    def _get_eta_matrix(self, resources, fires):
        """
        מחשבת מטריצת זמנים בעזרת OSRM Table API.
        שולחת בקשה מרוכזת אחת בלבד לכל הזירה! מוריד זמן ריצה מדקות לשניות בודדות.
        """
        matrix = {res.id: {} for res in resources}

        # 1. נאחד רכבים שיושבים באותה תחנה (כדי לחסוך קואורדינטות כפולות לשרת)
        stations_dict = {}  # מפתח: (אורך, רוחב), ערך: רשימת רכבים בתחנה הזו
        for res in resources:
            loc = (res.current_lon, res.current_lat)
            if loc not in stations_dict:
                stations_dict[loc] = []
            stations_dict[loc].append(res)

        unique_stations = list(stations_dict.keys())

        # 2. בניית מערך קואורדינטות: קודם כל התחנות (המקורות), ואז כל השריפות (היעדים)
        coords = [f"{lon},{lat}" for lon, lat in unique_stations]
        coords += [f"{fire.longitude},{fire.latitude}" for fire in fires]

        # יצירת האינדקסים (מי ברשימה הוא מקור ומי הוא יעד)
        # לדוגמה: אם יש 4 תחנות, האינדקסים שלהן הם 0;1;2;3
        sources_indices = ";".join(str(i) for i in range(len(unique_stations)))
        # אם יש 2 שריפות, האינדקסים שלהן הם 4;5
        dest_indices = ";".join(str(i + len(unique_stations)) for i in range(len(fires)))

        # 3. בניית ה-URL לשירות ה-Table
        coords_string = ";".join(coords)
        url = f"http://router.project-osrm.org/table/v1/driving/{coords_string}?sources={sources_indices}&destinations={dest_indices}"

        try:
            print(f"   🌐 שולח בקשת OSRM Table מרוכזת ({len(unique_stations)} מיקומי תחנות מול {len(fires)} יעדים)...")

            # משתמשים ב-SESSION שלנו שעובד מעולה!
            response = self.http_session.get(url, timeout=10.0)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == "Ok":
                # השרת מחזיר מטריצה (מערך דו-ממדי) של שניות
                durations = data["durations"]

                # 4. פענוח המטריצה ושיוך חזרה לכל רכב במערכת
                for i, station_loc in enumerate(unique_stations):
                    for j, fire in enumerate(fires):
                        duration_seconds = durations[i][j]

                        # השרת מחזיר None אם אין כביש (למשל מעבר לים/גבול)
                        if duration_seconds is not None:
                            eta_hours = duration_seconds / 3600.0  # המרה משניות לשעות!
                        else:
                            eta_hours = 999.0  # לא עביר

                        # מעדכנים את הזמן הזה ל*כל* הרכבים שיושבים באותה תחנה
                        for res in stations_dict[station_loc]:
                            matrix[res.id][fire.id] = eta_hours

                print("   ⚡ OSRM Table API: המטריצה כולה חזרה בהצלחה בקריאה אחת!")
                return matrix
            else:
                print(f"⚠️ שגיאה מהשרת: {data.get('code')}")

        except Exception as e:
            print(f"🔌 שגיאת OSRM Table API (עובר לגיבוי מתמטי): {e}")

        # ==========================================
        # מנגנון Fallback: אם ה-API נפל, נעשה מתמטיקה מהירה (אופליין)
        # ==========================================
        print("🔄 מחשב מטריצה בעזרת מנוע אופליין מקומי...")
        for res in resources:
            for fire in fires:
                dist_km = self._calculate_distance(res.current_lat, res.current_lon, fire.latitude, fire.longitude)
                eta_hours = (dist_km * 1.3) / 60.0
                matrix[res.id][fire.id] = eta_hours

        return matrix


    def run_master_cycle(self):
        """
        הלולאה האסטרטגית המרכזית (Time-First Architecture).
        """
        from app.models.fire_events import FireEvent
        from app.models.resources import Station
        from app.extensions import db
        from app.agents.predict_agent import FirePredictorAgent

        print("\n==================================================")
        print("🚀 מתחיל מחזור פיקוד אסטרטגי (Master Cycle)...")
        print("==================================================")

        cycle_start_time = time.time()

        # --- שלב 0: Setup והכנת זירות (מחוץ ללולאה) ---
        active_fires = FireEvent.query.filter(FireEvent.is_active == True).all()
        if not active_fires:
            print("✅ אין שריפות פעילות. חזרה לשגרה.")
            print(f"⏱️ Master Cycle הסתיים מוקדם (Early Return) תוך {time.time() - cycle_start_time:.2f} שניות.")
            return

        all_stations = Station.query.all()
        available_supply = self._fetch_available_resources()
        
        # בניית מילון זירות לפי מחוזות
        district_zones = {}
        for fire in active_fires:
            d_name = self._assign_district_to_fire(fire, all_stations)
            if d_name not in district_zones:
                district_zones[d_name] = []
            district_zones[d_name].append(fire)

        print(f"🗺️ המערכת קברצה {len(active_fires)} שריפות ל-{len(district_zones)} זירות מחוזיות.")

        allocated_in_this_cycle = set()
        allocated_yield_per_fire = {fire.id: 0.0 for fire in active_fires} # שמירת היסטוריית שיבוצים
        fire_demands = {fire.id: 0.0 for fire in active_fires}

        predictor = FirePredictorAgent()
        time_horizons = [1.0, 2.0, 3.0, 6.0, 12.0] # חלונות הזמן (בשעות)

        # --- הלולאה המרכזית (Spatio-Temporal Loop) ---
        for target_hours in time_horizons:
            step_start_time = time.time()

            # עצירה אם הכל נפתר
            if all(fire.is_active == False for fire in active_fires):
                print("🎯 כל הזירות בארץ קיבלו מענה מלא!")
                break

            print(f"\n⏳ פותח חלון זמן חיזוי ל-{target_hours} שעות קדימה...")

            # 1. חיזוי ודרישה מחדש לזמן הנוכחי
            try:
                predictor.run_cycle(target_hours=target_hours)
                self.step1_calculate_demands()
            except Exception as e:
                print(f"⚠️ שגיאה בהרצת חיזוי/דרישה: {e}")

            # 2. מעבר על כל זירה לבדיקת היתכנות
            for district_name, district_fires in district_zones.items():
                
                unsolved_fires = [f for f in district_fires if f.is_active]
                if not unsolved_fires:
                    continue # זירה זו נפתרה
                
                print(f"  📍 בודק זירת: {district_name} ({len(unsolved_fires)} שריפות פעילות)")

                # חישוב הדרישה נטו של הזירה
                total_district_demand = 0.0
                for fire in unsolved_fires:
                    db.session.refresh(fire) # מושכים את הדרישה המעודכנת שחושבה הרגע
                    updated_demand = getattr(fire, 'demand_perimeter_m', 0.0)
                    
                    # קיזוז תפוקה מכוחות שכבר שלחנו לשריפה הזו (כדי לא לבקש פעמיים)
                    current_demand = updated_demand - allocated_yield_per_fire[fire.id]
                    fire_demands[fire.id] = max(0, current_demand)
                    total_district_demand += fire_demands[fire.id]

                if total_district_demand <= 0:
                    for f in unsolved_fires: f.is_active = False
                    continue

                # --- שלב א': סינון מתמטי מהיר (מי מסוגל להגיע לזירה?) ---
                math_survivors = []
                for res_type, resources in available_supply.items():
                    if res_type == "ESHED": continue 
                    
                    for res in resources:
                        if res.id in allocated_in_this_cycle: continue
                        
                        # הגבלת מחוזות בשעה הראשונה
                        if target_hours <= 1.0 and res.station.district != district_name:
                            continue

                        # האם הכלי יכול להגיע לפחות לאחת השריפות בזירה בזמן?
                        can_reach = False
                        for fire in unsolved_fires:
                            dist = self._calculate_distance(fire.latitude, fire.longitude, res.current_lat, res.current_lon)
                            fast_eta = (dist * 1.4) / 60.0
                            if fast_eta < target_hours:
                                can_reach = True
                                break
                        
                        if can_reach:
                            math_survivors.append(res)

                # --- שלב ב': קבלת זמנים מדויקים מה-API ---
                eta_matrix = self._get_eta_matrix(math_survivors, unsolved_fires)

                # --- בדיקת היתכנות (Feasibility Check) ---
                total_potential_yield = 0.0
                
                for res in math_survivors:
                    # כדי להעריך פוטנציאל, נניח שהכלי ייסע לשריפה שאליה הוא מגיע הכי מהר
                    best_eta = min(eta_matrix[res.id][f.id] for f in unsolved_fires)
                    net_time = target_hours - best_eta
                    
                    if net_time > 0:
                        # חישוב תפוקה לשעה (נניח שריפה ראשונה כמייצגת SDI לטובת ההערכה)
                        hourly_yield = self.get_actual_yield(res.resource_type, unsolved_fires[0])
                        total_potential_yield += hourly_yield * net_time

                if total_potential_yield >= total_district_demand:
                    print(f"     ✅ נמצאה היתכנות! (היצע: {total_potential_yield:.1f} | ביקוש: {total_district_demand:.1f})")
                    
                    # הקריאה לשלב 4 האמיתי תבוא כאן!
                    # self.step4_optimize_and_dispatch(unsolved_fires, math_survivors, eta_matrix, ...)
                    
                    # בינתיים, לצורך השלד, נסמן את הזירה כפתורה כדי שהלולאה תתקדם
                    for f in unsolved_fires: f.is_active = False 
                else:
                    print(f"     ❌ אין מספיק כוח (חסר {total_district_demand - total_potential_yield:.1f} מטרים). ממתין להרחבת חלון הזמן.")

            step_elapsed = time.time() - step_start_time
            print(f"   ⏱️ חלון {target_hours}h הסתיים תוך {step_elapsed:.2f} שניות.")

        # --- כתיבה לדאטה-בייס ---
        try:
            db.session.commit()
            print("💾 מחזור הפיקוד הסתיים. שיבוצים נשמרו בהצלחה.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ שגיאה בשמירת השיבוצים: {e}")

        total_elapsed = time.time() - cycle_start_time
        print(f"\n⏱️ Master Cycle הסתיים תוך {total_elapsed:.2f} שניות סה\"כ.")

    def _get_driving_eta_minutes(self, start_lon, start_lat, dest_lon, dest_lat):
        """
        מחשב את זמן הנסיעה (ETA) בדקות בין שתי נקודות באמצעות OSRM API.
        כולל מנגנון Fallback לחישוב מרחק אווירי במקרה של כשל בשרת.
        """
        # בניית ה-URL לפי הסטנדרט של OSRM (קו אורך ואז קו רוחב)
        url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{dest_lon},{dest_lat}?overview=false"

        try:
            # הגדרת Timeout קשיח של 5 שניות. אסור למערכת שו"ב לחכות לנצח.
            response = self.http_session.get(url, timeout=5.0)

            # זורק חריגה (Exception) אם השרת החזיר קוד שגיאה כמו 404 או 500
            response.raise_for_status()

            data = response.json()

            # מוודאים שהבקשה הצליחה ושיש מסלול תקין בפלט
            if data.get("code") == "Ok" and len(data.get("routes", [])) > 0:
                # זמן הנסיעה חוזר בשניות, מחלקים ב-60 כדי לקבל דקות
                duration_seconds = data["routes"][0]["duration"]
                return duration_seconds / 60.0
            else:
                print(f"⚠️ OSRM API Warning: התקבלה תשובה לא תקינה מהשרת: {data.get('code')}")

        except requests.exceptions.RequestException as e:
            # תופס בעיות רשת, ניתוקים, Timeouts וכו'
            print(f"🔌 שגיאת תקשורת מול שרת הניווט (OSRM): {e}")

        # ==========================================
        # מנגנון Fallback (גיבוי חירום)
        # ==========================================
        print("🔄 מפעיל מנגנון גיבוי לחישוב ETA (מבוסס רדיוס ומהירות ממוצעת)...")

        # חישוב המרחק האווירי בקילומטרים (באמצעות הפונקציה הקיימת שלנו)
        # שים לב שפה הסדר הוא רוחב ואז אורך!
        distance_km = self._calculate_distance(start_lat, start_lon, dest_lat, dest_lon)

        # נניח מהירות נסיעה ממוצעת של 60 קמ"ש (קילומטר אחד לדקה)
        # נכפיל בפקטור של 1.3 כדי לפצות על זה שכבישים הם לא קו ישר (Tortuosity factor)
        average_speed_kpm = 60.0 / 60.0  # קילומטרים לדקה
        estimated_minutes = (distance_km / average_speed_kpm) * 1.3

        return estimated_minutes
