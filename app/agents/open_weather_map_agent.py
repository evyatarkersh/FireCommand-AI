import os
import requests
from app.extensions import db
# שים לב: וודא שהייבוא תואם לשם הקובץ בו שמרת את FireEvent
from app.models.fire_events import FireEvent

class WeatherService:
    def __init__(self):
        self.api_key = os.environ.get('OPENWEATHER_KEY')
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    def update_weather_for_event(self, event_id):
        """
        מקבל מיקום, פונה ל-API, ומחזיר מילון עם נתוני מזג אוויר מעובדים.
        """
        if not self.api_key:
            print("Error: OPENWEATHER_KEY is missing via .env")
            return None
        event = FireEvent.query.get(event_id)
        if not event:
            print(f"Event with ID {event_id} not found in DB.")
            return None
        lat = event.latitude
        lon = event.longitude


        # פרמטרים לבקשה: יחידות מטריות (צלזיוס)
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric'
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()

                # חישוב: המרה ממטר/שנייה לקמ"ש (כפל ב-3.6)
                # wind_speed_kph = data['wind']['speed'] * 3.6

                event.owm_wind_speed = data['wind']['speed']
                event.owm_wind_deg = data['wind']['deg']
                event.owm_temperature = data['main']['temp']
                event.owm_humidity = data['main']['humidity']

                try:
                    db.session.commit()
                    print(
                        f"Weather updated for Event #{event_id}: {event.owm_temperature}°C, Wind: {event.owm_wind_speed} km/h")
                    return True
                except Exception as db_err:
                    db.session.rollback()
                    print(f"Database Commit Error: {db_err}")
                    return False
            else:
                print(f"Weather API Error: {response.status_code}")
                return None

        except Exception as e:
            print(f"Connection Error to Weather API: {e}")
            return None