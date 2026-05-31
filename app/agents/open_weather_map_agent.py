import os
import time

import requests


class WeatherService:
    """Service for fetching weather data from OpenWeatherMap API and updating fire event objects with current weather conditions including wind speed, wind direction, temperature, and humidity."""

    def __init__(self):
        """Initialize the WeatherService with API credentials from environment variables and set the base URL for API requests."""
        self.api_key = os.environ.get('OPENWEATHER_KEY')
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    def update_weather_for_event(self, fire_event):
        """Update a FireEvent object with current weather data from OpenWeatherMap API using the event's coordinates, storing wind speed, wind direction, temperature, and humidity directly in the object without committing to database."""
        start_time = time.time()

        # Validate that the API key is configured
        if not self.api_key:
            print("❌ Error: OPENWEATHER_KEY is missing via .env")
            return None

        # Extract coordinates from the fire event object
        lat = fire_event.latitude
        lon = fire_event.longitude

        # Prepare API request parameters with metric units for Celsius temperature
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric'
        }

        try:
            # Send request to OpenWeatherMap API with timeout for safety
            response = requests.get(self.base_url, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()

                # Update the fire event object in memory with weather data
                fire_event.owm_wind_speed = data['wind']['speed']
                fire_event.owm_wind_deg = data['wind']['deg']
                fire_event.owm_temperature = data['main']['temp']
                fire_event.owm_humidity = data['main']['humidity']

                # Log successful weather update with timing information
                print(f"✅ Weather updated locally for Event #{fire_event.id}: {fire_event.owm_temperature}°C")
                total_time = time.time() - start_time
                print(f"   ⏱️ OWM agent took {total_time:.2f} seconds")
                return True

            else:
                print(f"⚠️ Weather API Error: {response.status_code}")
                return None

        except Exception as e:
            # Handle network errors gracefully to prevent system crashes
            print(f"⚠️ Connection Error to Weather API: {e}")
            total_time = time.time() - start_time
            print(f"   ⏱️ OWM agent failed after {total_time:.2f} seconds")
            return None
