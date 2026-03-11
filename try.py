from app.agents.llm_agent import LLMAgent
from datetime import datetime


def run_test():
    print("🚀 Initializing the LLM Agent...")
    agent = LLMAgent()

    if not agent.is_active:
        print("❌ Agent is inactive. Check your API Key.")
        return

    # נתוני דמה במבנה החדש שכולל סביבה, חיזוי מספרי ורמת סיכון
    mock_predictions = [
        {
            "event_id": 105,
            "location": "Lat 32.632, Lon 35.368",
            "environment": {
                "fuel_type": "Rangeland",
                "wind_speed_kmh": 25.5,
                "wind_direction_deg": 270,  # רוח מערבית
                "temperature_c": 32.0
            },
            "predictions": {
                "rate_of_spread_meters_per_hour": 950.0,
                "flame_length_meters": 3.2,
                "spread_direction_azimuth": 90,  # האש נדחפת מזרחה בגלל הרוח המערבית
                "risk_level": "HIGH",
                "prediction_timestamp": str(datetime.now())
            }
        },
        {
            "event_id": 108,
            "location": "Lat 31.768, Lon 35.213",
            "environment": {
                "fuel_type": "Trees",
                "wind_speed_kmh": 12.0,
                "wind_direction_deg": 360,  # רוח צפונית
                "temperature_c": 28.5
            },
            "predictions": {
                "rate_of_spread_meters_per_hour": 250.0,
                "flame_length_meters": 1.1,
                "spread_direction_azimuth": 180,  # האש נדחפת דרומה
                "risk_level": "MODERATE",
                "prediction_timestamp": str(datetime.now())
            }
        }
    ]

    print("📤 Sending advanced prediction data to the model (Groq/Llama-3.3)...")
    result = agent.summarize_predictions(mock_predictions)

    print("\n" + "=" * 50)
    print("📝 Tactical Situation Report:")
    print("=" * 50)
    print(result)
    print("=" * 50 + "\n")


if __name__ == "__main__":
    run_test()