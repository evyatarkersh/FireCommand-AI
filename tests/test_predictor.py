import pytest
import math
from unittest.mock import MagicMock
from app.agents.predict_agent import FirePredictorAgent


class MockEvent:
    """ אובייקט דמוי FireEvent לבדיקות יחידה מהירות """

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', 1)
        self.latitude = kwargs.get('lat', 32.0)
        self.longitude = kwargs.get('lon', 35.0)
        # נתונים מטאורולוגיים
        self.ims_wind_speed = kwargs.get('wind_speed', 10.0 / 3.6)  # מטר לשנייה
        self.ims_wind_dir = kwargs.get('wind_dir', 0.0)  # צפון
        self.ims_temp = kwargs.get('temp', 25.0)
        self.ims_humidity = kwargs.get('humidity', 50.0)
        self.ims_rain = kwargs.get('rain', 0.0)
        self.ims_wind_gust = kwargs.get('gust', self.ims_wind_speed)
        # נתונים סביבתיים
        self.fuel_load = kwargs.get('fuel', 1.0)
        self.topo_slope = kwargs.get('slope', 0.0)
        self.topo_aspect = kwargs.get('aspect', 0.0)
        # שדות פלט (שיעודכנו על ידי הסוכן)
        self.pred_ros = 0.0
        self.pred_risk_level = ""
        self.pred_direction = 0.0
        self.prediction_polygon = None
        self.prediction_summary = ""


def test_predictor_rain_stop():
    """ בדיקה שהגשם עוצר את התפשטות האש """
    predictor = FirePredictorAgent()
    predictor.llm_agent = MagicMock()  # ננטרל קריאות רשת ל-LLM

    event = MockEvent(rain=1.0)  # גשם חזק
    success = predictor._calculate_and_update(event, target_hours=1.0)

    assert success is True
    assert event.pred_ros == 0
    assert event.pred_risk_level == "LOW"
    # מוודא שנוצר פוליגון נקודתי (4 נקודות זהות)
    coords = event.prediction_polygon['coordinates'][0]
    assert coords[0] == [event.longitude, event.latitude]


def test_predictor_wind_logic():
    """ בדיקה שהרוח משפיעה נכון על כיוון וקצב האש """
    predictor = FirePredictorAgent()
    predictor.llm_agent = MagicMock()

    # רוח צפונית (0 מעלות) צריכה לדחוף את האש דרומה (180 מעלות)
    event = MockEvent(wind_dir=0.0, wind_speed=20.0 / 3.6, slope=0.0)
    predictor._calculate_and_update(event, target_hours=1.0)

    assert event.pred_direction == 180.0
    assert event.pred_ros > 0

    # בדיקה שרוח חזקה מאוד מגדילה את ה-ROS אבל לא עוברת את ה-Clamp
    event_storm = MockEvent(wind_speed=100.0 / 3.6)  # רוח מטורפת
    predictor._calculate_and_update(event_storm, target_hours=1.0)
    # ה-wind_factor המקסימלי הוא 4.5, אז ה-ROS צריך להיות מוגבל
    max_expected_ros = (1.0 * 40.0) * 4.5 * math.exp(0) * 1.0
    assert event_storm.pred_ros <= max_expected_ros + 1  # +1 לסטיית עיגול


def test_geometry_ellipse_creation():
    """ בדיקת תקינות ייצור ה-GeoJSON """
    predictor = FirePredictorAgent()

    # ניצור אליפסה ידנית דרך הפונקציה הפנימית
    # 100 מטר קדימה, 10 מטר אחורה, 30 מטר צדדים
    polygon = predictor._generate_ellipse_geojson(
        lat=32.0, lon=35.0, azimuth=90.0,
        head_m=100.0, back_m=10.0, flank_m=30.0
    )

    assert polygon['type'] == "Polygon"
    coords = polygon['coordinates'][0]

    # בדיקת סגירת הפוליגון (נקודה אחרונה שווה לראשונה)
    assert coords[0] == coords[-1]
    # בדיקת כמות נקודות (הגדרת 16 + נקודת סגירה = 17)
    assert len(coords) == 17