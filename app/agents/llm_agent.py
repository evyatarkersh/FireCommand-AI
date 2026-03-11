import os
import json
from groq import Groq
from groq.types.chat import ChatCompletionUserMessageParam


class LLMAgent:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            print("❌ LLM Agent Error: GROQ_API_KEY is missing.")
            self.is_active = False
            return

        self.client = Groq(api_key=self.api_key)
        self.model_name = "llama-3.3-70b-versatile"
        self.is_active = True

    def summarize_predictions(self, predictions_data):
        if not self.is_active:
            return "⚠️ LLM Agent is inactive."

        if not predictions_data:
            return "✅ No new predictions to summarize."

        print("🤖 LLM Agent: Translating prediction data into human-readable summary (via Groq)...")

        data_str = json.dumps(predictions_data, ensure_ascii=False, indent=2)

        prompt = f"""
        You are a seasoned Incident Commander in the Fire and Rescue Service. 
        You are provided with real-time prediction data for active wildfires.

        Data (JSON):
        {data_str}

        Task:
        Provide a concise, tactical Situation Report (SitRep) for the field units in English.
        For each event, include:

        * Event ID & Risk Level: State the ID and highlight the 'risk_level' (e.g., MODERATE, HIGH, EXTREME).
        * Fire Behavior: 
          - Translate the 'spread_direction_azimuth' into a compass direction (e.g., North-East).
          - Mention the Rate of Spread (ROS) in meters per hour.
          - State the 'flame_length_meters'. Explain briefly what this means tactically (e.g., "Flame lengths over 2.5m mean direct attack by ground crews is highly dangerous").
        * Driving Forces: Briefly mention how the 'fuel_type' and wind are affecting this prediction.

        Keep it brief, bulleted, and strictly based on the provided JSON. Do not invent metrics.
        """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    ChatCompletionUserMessageParam(
                        role="user",
                        content=prompt,
                    )
                ],
                model=self.model_name,
            )
            return chat_completion.choices[0].message.content

        except Exception as e:
            print(f"❌ LLM Agent Error: {e}")
            return "⚠️ Error generating the operational summary."