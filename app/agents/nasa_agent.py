import os
import requests
import csv
from io import StringIO
from datetime import datetime
from app.extensions import db
from app.models.nasa_fire import FireIncident
from app.agents.open_weather_map_agent import WeatherService


class NasaIngestionService:
    def __init__(self):
        self.api_key = os.environ.get('NASA_FIRMS_KEY')
        self.base_url = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
        # נשתמש ב-MODIS_SP לבדיקות היסטוריות, או VIIRS_..._NRT לזמן אמת
        # כרגע נשאיר את הרשימה שלך (VIIRS)
        self.sources = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]
        self.weather_service = WeatherService()


    def fetch_and_save_fires(self, days_back=1):
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
                    # 1. המרת זמן
                    date_str = row['acq_date']
                    time_str = row['acq_time'].zfill(4)
                    dt_object = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M")

                    # 2. המרת נתונים
                    lat = float(row['latitude'])
                    lon = float(row['longitude'])

                    # 3. בדיקה אם קיים ב-DB (מניעת כפילות לוגית)
                    exists = FireIncident.query.filter_by(
                        latitude=lat,
                        longitude=lon,
                        detected_at=dt_object,
                        source=source
                    ).first()

                    if not exists:
                        # 4. הוספה רק אם חדש
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

                # שמירת השינויים (Commit) בסוף כל לוויין
                db.session.commit()

            except Exception as e:
                db.session.rollback()
                print(f"Error processing {source}: {e}")

        return {"status": "success", "new_fires_added": new_records}