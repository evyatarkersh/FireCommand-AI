import math
import os
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta

from flask import current_app
from flask_socketio import SocketIO

from app.agents.IMS_DATA_agent import enrich_with_ims
from app.agents.commander_agent import CommanderAgent
from app.agents.fuel_agent import enrich_with_fuel
from app.agents.open_weather_map_agent import WeatherService
from app.agents.topo_agent import enrich_with_topography
from app.extensions import db
from app.models.fire_events import FireEvent
from app.models.nasa_fire import FireIncident


class MonitorAgent:
    """
    Monitors incoming fire incidents, clusters them into fire events using spatial proximity, enriches events with external data sources (weather, topography, IMS, fuel), and broadcasts updates to connected clients via WebSocket.
    """

    def __init__(self):
        """
        Initializes the MonitorAgent with weather service, clustering radius (2.5 km), and event timeout (24 hours).
        """
        self.weather_service = WeatherService()
        self.CLUSTER_RADIUS_KM = 2.5
        self.EVENT_TIMEOUT_HOURS = 24

    def run_cycle(self):
        """
        Executes a full monitoring cycle: fetches unprocessed fire incidents, clusters them into events based on spatial proximity, enriches each event with external data from multiple agents in parallel, commits changes to the database, broadcasts updates via WebSocket, and triggers the Commander Agent.
        """
        print("🕵️ Monitor Agent: Starting cycle...")

        # Fetch new raw data from unprocessed fire incidents
        unprocessed_reads = FireIncident.query.filter_by(is_processed=False).all()

        if not unprocessed_reads:
            print("Monitor: No new raw data.")
            return

        events_to_enrich = set()

        # Load active events into memory to avoid repeated database queries during clustering
        cutoff = datetime.utcnow() - timedelta(hours=self.EVENT_TIMEOUT_HOURS)
        self.active_events_cache = FireEvent.query.filter(FireEvent.last_update >= cutoff).all()

        print(f"Loaded {len(self.active_events_cache)} active events into memory cache.")

        # Iterate through records and perform spatial clustering
        for read in unprocessed_reads:
            matched_event = self._find_matching_event_in_memory(read)

            if matched_event:
                # Update existing event with new data
                self._update_existing_event(matched_event, read)
                read.event = matched_event
                events_to_enrich.add(matched_event)
                print(f" -> Merged read #{read.id} into Event #{matched_event.id}")
            else:
                # Create new event from incident
                new_event = self._create_new_event(read)
                db.session.add(new_event)
                db.session.flush()

                read.event = new_event
                events_to_enrich.add(new_event)

                # Add the new event to the in-memory cache for subsequent iterations
                self.active_events_cache.append(new_event)

                print(f" -> Created NEW Event #{new_event.id} from read #{read.id}")

            # Mark incident as processed
            read.is_processed = True

        # Save structural changes to database
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"❌ Monitor Error (Commit): {e}")
            return

        print(f"🌍 Enriching {len(events_to_enrich)} events with external data...")

        app = current_app._get_current_object()

        for event in events_to_enrich:
            # Execute enrichment with parallel threads for improved performance
            with ThreadPoolExecutor(max_workers=4) as executor:
                def run_in_context(func, target_event):
                    with app.app_context():
                        return func(target_event)

                # Submit all enrichment tasks to run in parallel for the current event
                futures = [
                    executor.submit(run_in_context, self.weather_service.update_weather_for_event, event),
                    executor.submit(run_in_context, enrich_with_topography, event),
                    executor.submit(run_in_context, enrich_with_ims, event),
                    executor.submit(run_in_context, enrich_with_fuel, event)
                ]

                # Wait for all enrichment tasks to complete before proceeding
                wait(futures)

                # Check if any enrichment agent encountered errors
                for future in futures:
                    if future.exception():
                        print(f"❌ Agent Error on event {event.id}: {future.exception()}")

        # Commit all enrichment changes to the database
        try:
            print("💾 Committing all changes to DB...")
            db.session.commit()
            print("✅ Monitor cycle finished and saved successfully.")

            print(f"📡 Broadcasting {len(events_to_enrich)} events to connected dashboards...")
            redis_url = os.environ.get('REDIS_URL')
            emitter = SocketIO(message_queue=redis_url) if redis_url else SocketIO()
            for event in events_to_enrich:
                fire_data = event.to_dict()
                emitter.emit('new_fire', fire_data)
                print("emitted event:", fire_data)
                emitter.sleep(1)
                print(f"✅ Broadcasted fire {event.id} to the network.")

        except Exception as e:
            db.session.rollback()
            print(f"❌ Monitor Error (Critical Commit Fail): {e}")
            return

        # Trigger Commander Agent to process the events
        self._trigger_commander_agent()

        print("✅ Monitor cycle finished.")

    def _find_matching_event_in_memory(self, read):
        """
        Searches for an existing fire event within the clustering radius of the given incident by iterating through the in-memory cache, and returns the closest matching event or None if no match is found.
        """
        closest, min_dist = None, float('inf')

        # Iterate over the in-memory cache instead of querying the database
        for event in self.active_events_cache:
            dist = self._calculate_distance(read.latitude, read.longitude, event.latitude, event.longitude)
            if dist < self.CLUSTER_RADIUS_KM:
                if dist < min_dist:
                    min_dist = dist
                    closest = event
        return closest

    def _create_new_event(self, read):
        """
        Creates a new FireEvent instance from a fire incident with initial geographic boundaries set to the single detection point, along with brightness, FRP, confidence, source, and timestamp data from the incident.
        """
        return FireEvent(
            latitude=read.latitude,
            longitude=read.longitude,
            # Initialize sector boundaries to the single detection point
            min_lat=read.latitude, max_lat=read.latitude,
            min_lon=read.longitude, max_lon=read.longitude,
            # Set initial statistics from the incident
            brightness=read.brightness,
            frp=read.frp,
            confidence=read.confidence,
            source=read.source,
            detected_at=read.detected_at,
            last_update=read.detected_at,
            num_points=1
        )

    def _update_existing_event(self, event, read):
        """
        Updates an existing fire event by expanding its geographic boundaries to include the new incident location, recalculating the center point, updating maximum intensity values (FRP and brightness), incrementing the detection count, and refreshing the last update timestamp.
        """
        # Expand sector boundaries to include the new detection point
        event.min_lat = min(event.min_lat, read.latitude)
        event.max_lat = max(event.max_lat, read.latitude)
        event.min_lon = min(event.min_lon, read.longitude)
        event.max_lon = max(event.max_lon, read.longitude)

        # Recalculate the center point as the average of the boundaries
        event.latitude = (event.min_lat + event.max_lat) / 2
        event.longitude = (event.min_lon + event.max_lon) / 2

        # Update intensity values to keep the maximum observed in the event
        if read.frp > event.frp:
            event.frp = read.frp
        if read.brightness > event.brightness:
            event.brightness = read.brightness

        # Update counters and timestamps
        event.num_points += 1
        event.last_update = datetime.utcnow()

    def _trigger_commander_agent(self):
        """
        Initiates the Commander Agent to process and respond to enriched fire events by calling its master cycle without parameters.
        """
        print(f"🔮 Triggering Commander Agent for events")
        commander = CommanderAgent()
        commander.run_master_cycle()

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """
        Calculates the great-circle distance in kilometers between two geographic coordinates using the Haversine formula, taking latitude and longitude pairs as input and returning the distance as a float.
        """
        # Haversine formula implementation
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(
            dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
