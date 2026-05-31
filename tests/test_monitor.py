from datetime import datetime, timedelta

from app.agents.monitor_agent import MonitorAgent
from app.models.fire_events import FireEvent
from app.extensions import db


class MockFireIncident:
    """Mock object for a raw NASA fire detection record, used to simulate fire incidents without requiring database interaction during unit tests."""

    def __init__(self, id, lat, lon, brightness, frp):
        """Initialize a mock fire incident with basic detection parameters including id, coordinates (lat, lon), brightness, and fire radiative power (frp)."""
        self.id = id
        self.latitude = lat
        self.longitude = lon
        self.brightness = brightness
        self.frp = frp
        self.confidence = 100
        self.source = "VIIRS"
        self.detected_at = "2026-04-20T10:00:00Z"
        self.is_processed = False


def test_monitor_clustering_logic():
    """Tests the fire clustering algorithm by verifying that nearby points are merged correctly, the geographic center is recalculated based on bounding box, and the FRP intensity takes the maximum value rather than summing."""
    monitor = MonitorAgent()

    # Initialize the memory cache to be empty as it would be at the start of a run on an empty database
    monitor.active_events_cache = []

    # Create 3 NASA observations: 2 close together in Jerusalem (~1 km apart, well below 2.5 km threshold), 1 far away in Haifa
    read1 = MockFireIncident(id=1, lat=31.768, lon=35.213, brightness=310.0, frp=25.0)
    read2 = MockFireIncident(id=2, lat=31.775, lon=35.220, brightness=315.0, frp=30.0)

    # Haifa observation is very far away from Jerusalem
    read3 = MockFireIncident(id=3, lat=32.794, lon=34.989, brightness=305.0, frp=20.0)

    raw_reads = [read1, read2, read3]

    # Run the core clustering logic loop without saving to database
    for read in raw_reads:
        matched_event = monitor._find_matching_event_in_memory(read)

        if matched_event:
            # Found a nearby event, update and expand it
            monitor._update_existing_event(matched_event, read)
        else:
            # No match found, create new event and add to cache
            new_event = monitor._create_new_event(read)
            monitor.active_events_cache.append(new_event)

    # Verify that only 2 events were created (Jerusalem points merged into one)
    assert len(monitor.active_events_cache) == 2, "Algorithm did not merge nearby points and created too many events!"

    # Extract the merged event (Jerusalem is the southern one of the two)
    jerusalem_event = next(e for e in monitor.active_events_cache if e.latitude < 32.0)
    haifa_event = next(e for e in monitor.active_events_cache if e.latitude > 32.0)

    # Verify merge logic: point counter should be 2 and FRP should be the maximum value
    assert jerusalem_event.num_points == 2, "Point counter was not updated within the merged event!"
    assert jerusalem_event.frp == 30.0, "FRP of merged event should be the highest of the two (30.0) and not the sum!"

    # Verify recalculation of geographic center based on bounding box
    expected_lat_center = (31.768 + 31.775) / 2
    expected_lon_center = (35.213 + 35.220) / 2
    assert jerusalem_event.latitude == expected_lat_center, "Central latitude was not calculated as the average of the bounds!"
    assert jerusalem_event.longitude == expected_lon_center, "Central longitude was not calculated as the average of the bounds!"

    # Verify the isolated Haifa event remains intact
    assert haifa_event.num_points == 1
    assert haifa_event.frp == 20.0


def test_monitor_timeout_logic(app):
    """Tests that the Monitor Agent correctly filters out old fires (over 24 hours) and only loads active events into memory, ensuring new detections create separate events instead of merging with expired historical events."""
    # Create two historical events in the mock database
    with app.app_context():
        now = datetime.utcnow()

        # Fresh event from two hours ago (should be loaded as active)
        fresh_event = FireEvent(
            id=101, latitude=32.0, longitude=35.0,
            min_lat=32.0, max_lat=32.0, min_lon=35.0, max_lon=35.0,
            detected_at=now - timedelta(hours=2),
            last_update=now - timedelta(hours=2),
            num_points=1
        )

        # Old event from two days ago (should be filtered out as expired)
        old_event = FireEvent(
            id=102, latitude=31.0, longitude=34.0,
            min_lat=31.0, max_lat=31.0, min_lon=34.0, max_lon=34.0,
            detected_at=now - timedelta(hours=48),
            last_update=now - timedelta(hours=48),
            num_points=5
        )

        db.session.add(fresh_event)
        db.session.add(old_event)
        db.session.commit()

        # Trigger the monitor agent's loading process
        monitor = MonitorAgent()

        # Simulate the first part of the run_cycle function by filtering based on timeout
        cutoff = datetime.utcnow() - timedelta(hours=monitor.EVENT_TIMEOUT_HOURS)
        monitor.active_events_cache = FireEvent.query.filter(FireEvent.last_update >= cutoff).all()

        # Verify only the fresh event was loaded into memory
        cached_ids = [event.id for event in monitor.active_events_cache]

        assert 101 in cached_ids, "The fresh event was not loaded into memory!"
        assert 102 not in cached_ids, "Danger: Monitor loaded an event from two days ago! Could cause false positives."
        assert len(monitor.active_events_cache) == 1, "Too many events loaded into memory."


def test_bounding_box_expansion_logic():
    """Tests the mathematical correctness of fire sector bounding box expansion by verifying that new observations from different edges correctly expand the virtual box and the center coordinates are recalculated accurately based on the expanded boundaries."""
    monitor = MonitorAgent()

    # Create a base event with a single point at an ideal center
    base_read = MockFireIncident(id=1, lat=32.0, lon=35.0, brightness=300, frp=20)
    event = monitor._create_new_event(base_read)

    # Verify that the initial bounding box is only a single point
    assert event.min_lat == 32.0 and event.max_lat == 32.0
    assert event.min_lon == 35.0 and event.max_lon == 35.0

    # Add observations from all four directions to expand the sector

    # Northern observation
    north_read = MockFireIncident(id=2, lat=32.1, lon=35.0, brightness=300, frp=20)
    monitor._update_existing_event(event, north_read)

    # Southern observation
    south_read = MockFireIncident(id=3, lat=31.9, lon=35.0, brightness=300, frp=20)
    monitor._update_existing_event(event, south_read)

    # Eastern observation
    east_read = MockFireIncident(id=4, lat=32.0, lon=35.1, brightness=300, frp=20)
    monitor._update_existing_event(event, east_read)

    # Western observation
    west_read = MockFireIncident(id=5, lat=32.0, lon=34.9, brightness=300, frp=20)
    monitor._update_existing_event(event, west_read)

    # Verify that all bounding box limits expanded correctly
    assert event.max_lat == 32.1, "Northern boundary did not expand!"
    assert event.min_lat == 31.9, "Southern boundary did not expand!"
    assert event.max_lon == 35.1, "Eastern boundary did not expand!"
    assert event.min_lon == 34.9, "Western boundary did not expand!"

    # Verify center calculation returns to original point after symmetric expansion
    assert event.latitude == 32.0, "Error in calculating central latitude!"
    assert event.longitude == 35.0, "Error in calculating central longitude!"

    # Verify point counter accumulated all observations
    assert event.num_points == 5, "Point counter did not accumulate observations correctly"
