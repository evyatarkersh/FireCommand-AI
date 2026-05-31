import csv
import json
import os
from datetime import datetime
from io import StringIO

import requests
from shapely.geometry import Point, shape

from app.agents.open_weather_map_agent import WeatherService
from app.extensions import db
from app.models.nasa_fire import FireIncident


class NasaIngestionService:
    """Service for ingesting and processing fire incident data from NASA FIRMS API. Fetches fire detections from multiple VIIRS satellite sources, filters them spatially within Israel's borders, and stores validated incidents in the database."""

    def __init__(self):
        """Initializes the NASA ingestion service with API credentials, satellite data sources, weather service integration, and Israel's geographic boundary polygon for spatial filtering."""
        self.api_key = os.environ.get('NASA_FIRMS_KEY')
        self.base_url = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
        # MODIS_SP available for historical data, VIIRS_NRT sources for real-time detection
        self.sources = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]
        self.weather_service = WeatherService()
        self.israel_polygon = self._load_israel_polygon()

    def _load_israel_polygon(self):
        """Loads Israel's geographic boundary polygon from the GeoJSON file. Returns a Shapely shape object representing the country's borders for spatial filtering, or None if the file cannot be loaded."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        geojson_path = os.path.join(current_dir, '..', 'data', 'israel_borders.geojson')
        try:
            with open(geojson_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
                return shape(geojson_data['features'][0]['geometry'])
        except Exception as e:
            print(f"Warning: Failed to load Israel polygon: {e}")
            return None

    def fetch_and_save_fires(self, days_back=1):
        """Fetches fire detection data from NASA FIRMS API for the specified number of days back, processes each satellite source, filters points within Israel's borders, and saves new fire incidents to the database. Returns a dictionary with the operation status and count of newly added records."""
        if not self.api_key:
            return {"error": "No API Key"}

        israel_bbox = "34.2654333839,29.5013261988,35.8363969256,33.2774264593"
        new_records = 0

        for source in self.sources:
            url = f"{self.base_url}/{self.api_key}/{source}/{israel_bbox}/{days_back}"

            try:
                response = requests.get(url)
                if response.status_code != 200 or response.text.count('\n') <= 1:
                    continue

                csv_data = StringIO(response.text)
                reader = csv.DictReader(csv_data)

                for row in reader:
                    # Convert latitude and longitude to float for spatial operations
                    lat = float(row['latitude'])
                    lon = float(row['longitude'])

                    # Apply spatial filtering to exclude points outside Israel's borders
                    if self.israel_polygon:
                        if not self.israel_polygon.contains(Point(lon, lat)):
                            # Point is in sea or outside borders - skip to next CSV row
                            continue

                    # Parse acquisition date and time into datetime object
                    date_str = row['acq_date']
                    time_str = row['acq_time'].zfill(4)
                    dt_object = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M")

                    # Check if this fire incident already exists in the database
                    exists = FireIncident.query.filter_by(
                        latitude=lat,
                        longitude=lon,
                        detected_at=dt_object,
                        source=source
                    ).first()

                    if not exists:
                        # Create and add new fire incident record
                        fire = FireIncident(
                            latitude=lat,
                            longitude=lon,
                            brightness=float(row.get('bright_ti4', 0)),
                            frp=float(row.get('frp', 0)),
                            confidence=row.get('confidence', 'n/a'),
                            source=source,
                            detected_at=dt_object
                        )
                        db.session.add(fire)
                        new_records += 1

                # Commit all changes for the current satellite source
                db.session.commit()

            except Exception as e:
                db.session.rollback()
                print(f"Error processing {source}: {e}")

        return {"status": "success", "new_fires_added": new_records}
