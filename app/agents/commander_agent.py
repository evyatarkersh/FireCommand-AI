import math


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
            matrix = {"ROTEM": 1.0, "SAAR": 1.0, "AIR_TRACTOR": 1.0, "ESHED": 1.0}

        return matrix.get(resource_type, 0.0)

    def get_actual_yield(self, resource_type, event):
        """ מחשב את התפוקה האמיתית של רכב ספציפי באירוע ספציפי (מטרים/שעה). """
        terrain = self._determine_terrain(event.fuel_type)
        slope = getattr(event, 'slope', 0.0)

        base_rate = self.BASE_PRODUCTION_RATES.get(resource_type, 0.0)
        sdi_factor = self._calculate_sdi_factor(resource_type, terrain, slope)

        return base_rate * sdi_factor

    def _fetch_available_resources(self):
        """ שולף את כל המשאבים הפנויים ממסד הנתונים פעם אחת בלבד ומסדר אותם לפי סוג. """
        from app.models.resources import Resource
        available_resources = Resource.query.filter_by(status='AVAILABLE').all()

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

    def run_master_cycle(self):
        """
        הלולאה האסטרטגית המרכזית.
        מאתרת שריפות, פותחת רדיוסים גיאוגרפיים, משבצת כוחות, ומעדכנת חיזויים.
        """
        from app.models.fire_events import FireEvent
        from app.extensions import db

        print("🚀 מתחיל מחזור פיקוד אסטרטגי (Master Cycle)...")

        # --- שלב 1: איסוף נתונים לזיכרון (Setup) ---
        active_fires = FireEvent.query.filter(FireEvent.is_active == True).all()
        if not active_fires:
            print("✅ אין שריפות פעילות. חזרה לשגרה.")
            return

        available_supply = self._fetch_available_resources()
        allocated_in_this_cycle = set()
        fire_demands = {}

        # מעקב אחר כמות רכבי ה'סער' שגויסו לכל שריפה (עבור נוהל ה-Enabler)
        saar_counters = {fire.id: 0 for fire in active_fires}

        # --- שלב 2: חישוב דרישה ראשוני (Initial Demand) ---
        for fire in active_fires:
            fire_demands[fire.id] = self._partner_mock_calculate_demand(fire, minutes_ahead=15)

        search_rings = [15.0, 30.0, 60.0, 120.0]

        # --- שלב 3: לולאת המרחב-זמן (Spatio-Temporal Loop) ---
        for ring_radius in search_rings:

            if all(demand <= 0 for demand in fire_demands.values()):
                print("🎯 כל מוקדי האש קיבלו מענה מלא!")
                break

            print(f"\n🌍 פותח רדיוס סריקה: {ring_radius} ק\"מ...")

            sorted_fires = sorted(active_fires, key=lambda f: getattr(f, 'pred_risk_level', 'LOW'), reverse=True)

            for fire in sorted_fires:
                current_demand = fire_demands[fire.id]
                if current_demand <= 0:
                    continue

                for res_type, resources in available_supply.items():
                    # ה-ESHED מנוהל על ידי ה-Enabler בלבד, נדלג עליו בלולאה הרגילה
                    if res_type == "ESHED":
                        continue

                    for res in resources:
                        if res.id in allocated_in_this_cycle:
                            continue

                        dist = self._calculate_distance(fire.latitude, fire.longitude, res.current_lat, res.current_lon)

                        if dist <= ring_radius:
                            actual_yield = self.get_actual_yield(res_type, fire)

                            if actual_yield > 0:
                                res.status = 'EN_ROUTE'
                                res.assigned_event_id = fire.id
                                allocated_in_this_cycle.add(res.id)

                                current_demand -= actual_yield
                                fire_demands[fire.id] = current_demand

                                print(
                                    f"🚒 שובץ רכב {res_type} (תפוקה: {actual_yield:.1f}) לשריפה {fire.id}. נותר לסגור: {max(0, current_demand):.1f}")

                                # מנגנון ה-Enabler: בודק אם צריך להקפיץ אשד
                                if res_type == "SAAR":
                                    saar_counters[fire.id] += 1
                                    if saar_counters[fire.id] % 3 == 0:
                                        self._allocate_enabler_eshed(fire, available_supply["ESHED"],
                                                                     allocated_in_this_cycle)

                                if current_demand <= 0:
                                    break

                    if current_demand <= 0:
                        break

            if any(demand > 0 for demand in fire_demands.values()) and ring_radius != search_rings[-1]:
                print("⏳ חסרים כוחות. מעדכן חיזוי (Prediction) לזמן ההגעה של הרדיוס הבא...")
                for fire in active_fires:
                    if fire_demands[fire.id] > 0:
                        new_demand = self._partner_mock_calculate_demand(fire, minutes_ahead=30)
                        fire_demands[fire.id] = new_demand

        # --- שלב 4: כתיבה לדאטה-בייס (Commit) ---
        try:
            db.session.commit()
            print("\n💾 השיבוצים נשמרו בהצלחה למסד הנתונים.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ שגיאה בשמירת השיבוצים: {e}")

    def _partner_mock_calculate_demand(self, event, minutes_ahead):
        """ פונקציית פלייסחולדר עד לחיבור לוגיקת הפוליגונים """
        return 1500.0