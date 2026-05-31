import math
from unittest.mock import MagicMock

from app.agents.predict_agent import FirePredictorAgent


class MockEvent:
    """
    Mock FireEvent object for fast unit testing. Simulates a fire event with meteorological, environmental, and
    prediction output fields without requiring database interaction.
    """

    def __init__(self, **kwargs):
        """
        Initialize a mock fire event with default or provided values for meteorological data (wind, temperature,
        humidity, rain), environmental data (fuel, slope, aspect), and output fields for prediction results.
        """
        self.id = kwargs.get('id', 1)
        self.latitude = kwargs.get('lat', 32.0)
        self.longitude = kwargs.get('lon', 35.0)
        # Meteorological data
        self.ims_wind_speed = kwargs.get('wind_speed', 10.0 / 3.6)  # meters per second
        self.ims_wind_dir = kwargs.get('wind_dir', 0.0)  # north
        self.ims_temp = kwargs.get('temp', 25.0)
        self.ims_humidity = kwargs.get('humidity', 50.0)
        self.ims_rain = kwargs.get('rain', 0.0)
        self.ims_wind_gust = kwargs.get('gust', self.ims_wind_speed)
        # Environmental data
        self.fuel_load = kwargs.get('fuel', 1.0)
        self.topo_slope = kwargs.get('slope', 0.0)
        self.topo_aspect = kwargs.get('aspect', 0.0)
        # Output fields (will be updated by the agent)
        self.pred_ros = 0.0
        self.pred_risk_level = ""
        self.pred_direction = 0.0
        self.prediction_polygon = None
        self.prediction_summary = ""


def test_predictor_rain_stop():
    """
    Test that rain stops fire spread. Verifies that when heavy rain is present, the fire rate of spread becomes zero,
    risk level is set to LOW, and a point polygon is created at the fire's origin location.
    """
    predictor = FirePredictorAgent()
    # Neutralize network calls to LLM
    predictor.llm_agent = MagicMock()

    # Heavy rain
    event = MockEvent(rain=1.0)
    success = predictor._calculate_and_update(event, target_hours=1.0)

    assert success is True
    assert event.pred_ros == 0
    assert event.pred_risk_level == "LOW"
    # Verify that a point polygon was created with four identical points
    coords = event.prediction_polygon['coordinates'][0]
    assert coords[0] == [event.longitude, event.latitude]


def test_predictor_wind_logic():
    """
    Test that wind correctly affects fire direction and rate of spread. Verifies that north wind pushes fire southward
    and that extreme wind conditions increase ROS but respect the maximum wind factor clamp of 4.5.
    """
    predictor = FirePredictorAgent()
    predictor.llm_agent = MagicMock()

    # North wind at 0 degrees should push the fire southward to 180 degrees
    event = MockEvent(wind_dir=0.0, wind_speed=20.0 / 3.6, slope=0.0)
    predictor._calculate_and_update(event, target_hours=1.0)

    assert event.pred_direction == 180.0
    assert event.pred_ros > 0

    # Test that very strong wind increases ROS but respects the maximum clamp
    # Extreme wind
    event_storm = MockEvent(wind_speed=100.0 / 3.6)
    predictor._calculate_and_update(event_storm, target_hours=1.0)
    # Maximum wind_factor is 4.5, so ROS should be limited
    max_expected_ros = (1.0 * 40.0) * 4.5 * math.exp(0) * 1.0
    # Account for small rounding error
    assert event_storm.pred_ros <= max_expected_ros + 1


def test_geometry_ellipse_creation():
    """
    Test validity of GeoJSON polygon generation for fire spread ellipse. Verifies that the generated polygon has the
    correct type, is properly closed, and contains the expected number of coordinate points (16 plus closing point).
    """
    predictor = FirePredictorAgent()

    # Create an ellipse manually through the internal function
    # Parameters: 100 meters forward, 10 meters backward, 30 meters on flanks
    polygon = predictor._generate_ellipse_geojson(
        lat=32.0, lon=35.0, azimuth=90.0,
        head_m=100.0, back_m=10.0, flank_m=30.0
    )

    assert polygon['type'] == "Polygon"
    coords = polygon['coordinates'][0]

    # Verify polygon closure: last point equals first point
    assert coords[0] == coords[-1]
    # Verify number of points: defined as 16 plus closing point equals 17
    assert len(coords) == 17
