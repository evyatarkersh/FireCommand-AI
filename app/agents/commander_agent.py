from shapely.geometry import shape
from pyproj import Geod
from app.extensions import db
from app.models.fire_events import FireEvent

class CommanderAgent:
    """
    סוכן המפקד: מבצע אופטימיזציית משאבים מבוססת תפוקת קו הגנה (Production Rate)
    ומדד קושי דיכוי מבצעי (SDI).
    """

    # חלק 2: תפוקת מעבדה בסיסית (מטרים של קו הגנה בשעה)
    BASE_PRODUCTION_RATES = {
        "ROTEM": 800.0,  # תקיפה בתנועה (Pump-and-Roll)
        "SAAR": 300.0,  # פריסת זרנוקים איטית בשטח
        "AIR_TRACTOR": 2000.0,  # הטלה אווירית מהירה
        "ESHED": 0.0  # מאפשר (Enabler) - לא בונה קו אש בעצמו
    }

    def __init__(self):
        # הגדרת אובייקט מתמטי לחישוב מרחקים על פני כדור הארץ במטרים (WGS84)
        self.geod = Geod(ellps="WGS84")

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
                # יער תלול - שטח רע לכלי רכב כבדים
                matrix = {
                    "ROTEM": 0.7,  # מתקשה אבל מטפס
                    "SAAR": 0.0,  # גזר דין מוות, נפסל
                    "AIR_TRACTOR": 0.9,  # מסוכן מעט, אבל אפשרי
                    "ESHED": 0.0  # יתהפך, נפסל
                }
            else:
                # יער מישורי - עבירות טובה יותר
                matrix = {
                    "ROTEM": 1.0,  # סביבה אידיאלית
                    "SAAR": 0.4,  # יכול להגיע רק לשבילים הראשיים
                    "AIR_TRACTOR": 1.0,  # אידיאלי
                    "ESHED": 0.5  # מתקדם לאט על שבילי כורכר
                }
        elif terrain == "URBAN":
            # שטח עירוני - משנה לחלוטין את חוקי המשחק
            matrix = {
                "ROTEM": 0.5,  # מעט מדי מים למבנים, יעיל רק ככוח עזר
                "SAAR": 1.0,  # הסביבה הטבעית שלו
                "AIR_TRACTOR": 0.0,  # אסור להטיל מעל אוכלוסייה! נפסל
                "ESHED": 1.0  # אידיאלי לתמיכת מים מול הידרנטים
            }
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
        slope = getattr(event, 'topo_slope', 0.0) 

        base_rate = self.BASE_PRODUCTION_RATES.get(resource_type, 0.0)
        sdi_factor = self._calculate_sdi_factor(resource_type, terrain, slope)

        actual_yield = base_rate * sdi_factor
        return actual_yield