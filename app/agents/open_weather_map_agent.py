import os
import requests
# שימ לב: אין צורך לייבא את db או את המודל בתוך הפונקציה הזו יותר,
# כי אנחנו לא שולפים ולא שומרים, רק מעדכנים אובייקט קיים.

class WeatherService:
    def __init__(self):
        self.api_key = os.environ.get('OPENWEATHER_KEY')
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    def update_weather_for_event(self, fire_event):
        """
        מקבל אובייקט FireEvent (בזיכרון), פונה ל-API, ומעדכן את השדות.
        ללא Commit ל-DB!
        """
        # בדיקה שיש מפתח API
        if not self.api_key:
            print("❌ Error: OPENWEATHER_KEY is missing via .env")
            return None
        
        # 1. שימוש בקואורדינטות מתוך האובייקט
        lat = fire_event.latitude
        lon = fire_event.longitude

        # פרמטרים לבקשה: יחידות מטריות (צלזיוס)
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric'
        }

        try:
            # הוספנו Timeout ליתר ביטחון
            response = requests.get(self.base_url, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()

                # 2. עדכון האובייקט בזיכרון (ללא SQL)
                fire_event.owm_wind_speed = data['wind']['speed']
                fire_event.owm_wind_deg = data['wind']['deg']
                fire_event.owm_temperature = data['main']['temp']
                fire_event.owm_humidity = data['main']['humidity']

                # 3. אין Commit! רק הודעת הצלחה
                print(f"✅ Weather updated locally for Event #{fire_event.id}: {fire_event.owm_temperature}°C")
                return True

            else:
                print(f"⚠️ Weather API Error: {response.status_code}")
                return None

        except Exception as e:
            # תופסים שגיאות רשת כדי לא להפיל את המוניטור
            print(f"⚠️ Connection Error to Weather API: {e}")
            return None