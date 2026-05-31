from app.agents.commander_agent import CommanderAgent


def test_calculate_distance():
    """
    Tests the Haversine distance calculation function by verifying zero distance for identical points and sanity-checking the Tel Aviv to Jerusalem distance (approximately 54 km).
    """
    commander = CommanderAgent()

    # Zero test: distance between a point and itself must be 0
    dist_zero = commander._calculate_distance(32.0, 34.0, 32.0, 34.0)
    assert dist_zero == 0.0

    # Sanity check: distance from Tel Aviv (32.08, 34.78) to Jerusalem (31.76, 35.21)
    # The actual straight-line distance is approximately 54 km, verify it's in a reasonable range (50-60)
    dist_ta_jer = commander._calculate_distance(32.0853, 34.7818, 31.7683, 35.2137)
    assert 50.0 < dist_ta_jer < 60.0


def test_calculate_sdi_factor():
    """
    Tests the terrain traversability penalty (SDI) calculation function by verifying that it returns the correct coefficients according to the traversability matrix for various resource types, terrain types, and slope conditions.
    """
    commander = CommanderAgent()

    # Fallback terrain (GRASS or anything that is not forest/urban) should return 1.0 for all resources
    sdi_grass = commander._calculate_sdi_factor(resource_type="SAAR", terrain="GRASS", slope=0.0)
    assert sdi_grass == 1.0

    # Forest (FOREST) in normal conditions (slope <= 15)
    assert commander._calculate_sdi_factor("ROTEM", "FOREST", 10.0) == 1.0
    assert commander._calculate_sdi_factor("SAAR", "FOREST", 10.0) == 0.4
    assert commander._calculate_sdi_factor("ESHED", "FOREST", 10.0) == 0.5

    # Steep forest (FOREST) (slope > 15)
    assert commander._calculate_sdi_factor("ROTEM", "FOREST", 20.0) == 0.7
    # SAAR is not traversable on steep slope in forest
    assert commander._calculate_sdi_factor("SAAR", "FOREST", 20.0) == 0.0
    assert commander._calculate_sdi_factor("AIR_TRACTOR", "FOREST", 20.0) == 0.9

    # Urban area (URBAN)
    # SAAR is excellent in urban areas
    assert commander._calculate_sdi_factor("SAAR", "URBAN", 0.0) == 1.0
    # ROTEM is bulky in urban areas
    assert commander._calculate_sdi_factor("ROTEM", "URBAN", 0.0) == 0.5
    # Cannot drop water inside urban areas
    assert commander._calculate_sdi_factor("AIR_TRACTOR", "URBAN", 0.0) == 0.0


from unittest.mock import MagicMock


def test_get_actual_yield():
    """
    Tests the actual yield calculation (get_actual_yield) by verifying that the function correctly multiplies the base production rate by the SDI factor and handles edge cases such as missing slope data in the database.
    """
    commander = CommanderAgent()

    # Set fixed production rates for the test to make it deterministic
    commander.BASE_PRODUCTION_RATES = {
        "ROTEM": 400.0,
        "SAAR": 300.0
    }

    # Neutralize the function that translates fuel to terrain (assume it simply returns what it receives)
    commander._determine_terrain = MagicMock(side_effect=lambda fuel: fuel)

    # Create a lightweight mock class that simulates the behavior of the FireEvent model
    class MockEvent:
        """
        Lightweight mock class that simulates the FireEvent model with fuel_type and topo_slope attributes for testing purposes.
        """
        def __init__(self, fuel_type, topo_slope):
            self.fuel_type = fuel_type
            self.topo_slope = topo_slope

    # Scenario 1: Open area (GRASS), no slope (expected SDI: 1.0)
    # SAAR should produce: 300 * 1.0 = 300
    grass_event = MockEvent(fuel_type="GRASS", topo_slope=0.0)
    assert commander.get_actual_yield("SAAR", grass_event) == 300.0

    # Scenario 2: Non-steep forest (FOREST, slope 10)
    # SDI ROTEM=1.0, SDI SAAR=0.4
    forest_flat_event = MockEvent(fuel_type="FOREST", topo_slope=10.0)
    # 400 * 1.0
    assert commander.get_actual_yield("ROTEM", forest_flat_event) == 400.0
    # 300 * 0.4
    assert commander.get_actual_yield("SAAR", forest_flat_event) == 120.0

    # Scenario 3: Steep forest (FOREST, slope 20)
    # SDI ROTEM=0.7, SDI SAAR=0.0
    forest_steep_event = MockEvent(fuel_type="FOREST", topo_slope=20.0)
    # 400 * 0.7
    assert commander.get_actual_yield("ROTEM", forest_steep_event) == 280.0
    # 300 * 0.0
    assert commander.get_actual_yield("SAAR", forest_steep_event) == 0.0

    # Scenario 4: Handling missing database information (None)
    # The function should convert None to 0.0 slope
    # In an urban environment, ROTEM's coefficient is 0.5
    urban_event_no_slope = MockEvent(fuel_type="URBAN", topo_slope=None)
    # 400 * 0.5
    assert commander.get_actual_yield("ROTEM", urban_event_no_slope) == 200.0
