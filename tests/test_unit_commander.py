import pytest
from app.agents.commander_agent import CommanderAgent


def test_calculate_distance():
    """
    בדיקת יחידה: פונקציית חישוב מרחק בקו אווירי (Haversine)
    """
    commander = CommanderAgent()

    # 1. בדיקת אפס: מרחק בין נקודה לעצמה חייב להיות 0
    dist_zero = commander._calculate_distance(32.0, 34.0, 32.0, 34.0)
    assert dist_zero == 0.0

    # 2. בדיקת שפיות: מרחק מתל אביב (32.08, 34.78) לירושלים (31.76, 35.21)
    # המרחק האמיתי בקו אווירי הוא בערך 54 ק"מ. נוודא שהוא בטווח הגיוני (50-60).
    dist_ta_jer = commander._calculate_distance(32.0853, 34.7818, 31.7683, 35.2137)
    assert 50.0 < dist_ta_jer < 60.0


def test_calculate_sdi_factor():
    """
    בדיקת יחידה: פונקציית חישוב קנס העבירות בשטח (SDI)
    מוודא שהפונקציה מחזירה את המקדמים המדויקים לפי מטריצת העבירות שמוגדרת בקוד.
    """
    commander = CommanderAgent()

    # 1. Fallback (GRASS או כל מה שאינו יער/אורבני) - מצפים ל-1.0 לכולם
    sdi_grass = commander._calculate_sdi_factor(resource_type="SAAR", terrain="GRASS", slope=0.0)
    assert sdi_grass == 1.0

    # 2. יער (FOREST) במצב רגיל (slope <= 15)
    assert commander._calculate_sdi_factor("ROTEM", "FOREST", 10.0) == 1.0
    assert commander._calculate_sdi_factor("SAAR", "FOREST", 10.0) == 0.4
    assert commander._calculate_sdi_factor("ESHED", "FOREST", 10.0) == 0.5

    # 3. יער (FOREST) תלול (slope > 15)
    assert commander._calculate_sdi_factor("ROTEM", "FOREST", 20.0) == 0.7
    assert commander._calculate_sdi_factor("SAAR", "FOREST", 20.0) == 0.0  # סער לא עביר בשיפוע חד ביער
    assert commander._calculate_sdi_factor("AIR_TRACTOR", "FOREST", 20.0) == 0.9

    # 4. שטח בנוי (URBAN)
    assert commander._calculate_sdi_factor("SAAR", "URBAN", 0.0) == 1.0  # סער מצוין בעיר
    assert commander._calculate_sdi_factor("ROTEM", "URBAN", 0.0) == 0.5  # רותם מגושם בעיר
    assert commander._calculate_sdi_factor("AIR_TRACTOR", "URBAN", 0.0) == 0.0  # אי אפשר להטיל מים בתוך עיר


from unittest.mock import MagicMock


def test_get_actual_yield():
    """
    בדיקת יחידה: חישוב תפוקה בפועל (get_actual_yield)
    מוודא שהפונקציה מכפילה נכון את קצב הייצור הבסיסי בפקטור ה-SDI,
    ומטפלת נכון במקרי קצה (כמו שיפוע שחסר במסד הנתונים).
    """
    commander = CommanderAgent()

    # 1. עיקור תלויות (Mocking):
    # נקבע קצבי ייצור קבועים לטסט כדי שהוא יהיה דטרמיניסטי לעד
    commander.BASE_PRODUCTION_RATES = {
        "ROTEM": 400.0,
        "SAAR": 300.0
    }

    # ננטרל את הפונקציה שמתרגמת דלק לשטח (נניח שהיא פשוט מחזירה את מה שקיבלה)
    commander._determine_terrain = MagicMock(side_effect=lambda fuel: fuel)

    # נייצר מחלקה מזויפת וקלילה שתחקה את התנהגות מודל ה-FireEvent
    class MockEvent:
        def __init__(self, fuel_type, topo_slope):
            self.fuel_type = fuel_type
            self.topo_slope = topo_slope

    # === מבחני התוצאה ===

    # תרחיש 1: שטח פתוח (GRASS), ללא שיפוע. (SDI צפוי: 1.0)
    # SAAR אמור להפיק: 300 * 1.0 = 300
    grass_event = MockEvent(fuel_type="GRASS", topo_slope=0.0)
    assert commander.get_actual_yield("SAAR", grass_event) == 300.0

    # תרחיש 2: יער לא תלול (FOREST, שיפוע 10).
    # לפי הקוד שלך: SDI רותם=1.0, SDI סער=0.4
    forest_flat_event = MockEvent(fuel_type="FOREST", topo_slope=10.0)
    assert commander.get_actual_yield("ROTEM", forest_flat_event) == 400.0  # 400 * 1.0
    assert commander.get_actual_yield("SAAR", forest_flat_event) == 120.0  # 300 * 0.4

    # תרחיש 3: יער תלול (FOREST, שיפוע 20).
    # לפי הקוד שלך: SDI רותם=0.7, SDI סער=0.0
    forest_steep_event = MockEvent(fuel_type="FOREST", topo_slope=20.0)
    assert commander.get_actual_yield("ROTEM", forest_steep_event) == 280.0  # 400 * 0.7
    assert commander.get_actual_yield("SAAR", forest_steep_event) == 0.0  # 300 * 0.0

    # תרחיש 4: התמודדות עם מידע חסר במסד (None)
    # הפונקציה אמורה להפוך את ה-None ל-0.0 שיפוע.
    # בסביבה עירונית מקדם הרותם הוא 0.5.
    urban_event_no_slope = MockEvent(fuel_type="URBAN", topo_slope=None)
    assert commander.get_actual_yield("ROTEM", urban_event_no_slope) == 200.0  # 400 * 0.5