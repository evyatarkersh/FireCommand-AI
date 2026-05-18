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
        
        # 1. הגדרת שני המודלים שלנו (המועדף והגיבוי)
        self.primary_model = "llama-3.3-70b-versatile" # המודל החזק, החכם (והיקר)
        self.fallback_model = "llama-3.1-8b-instant"   # המודל הקטן, המהיר (לגיבוי)
        
        self.is_active = True

    def _call_llm_with_fallback(self, prompt, context_name="LLM"):
        """
        פונקציית עזר פנימית שמנהלת את הניסיונות מול Groq.
        מנסה קודם את המודל הראשי. אם נכשל, עוברת אוטומטית לגיבוי.
        """
        try:
            # ניסיון 1: המודל הראשי (70B)
            chat_completion = self.client.chat.completions.create(
                messages=[ChatCompletionUserMessageParam(role="user", content=prompt)],
                model=self.primary_model,
            )
            return chat_completion.choices[0].message.content

        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ {context_name}: Primary model ({self.primary_model}) failed. Reason: {error_msg}")
            
            # אם השגיאה היא Rate Limit או סתם עומס, נפעיל את הגיבוי
            print(f"🔄 {context_name}: Falling back to backup model ({self.fallback_model})...")
            
            try:
                # ניסיון 2: מודל הגיבוי (8B)
                chat_completion_fallback = self.client.chat.completions.create(
                    messages=[ChatCompletionUserMessageParam(role="user", content=prompt)],
                    model=self.fallback_model,
                )
                return chat_completion_fallback.choices[0].message.content
                
            except Exception as fallback_error:
                print(f"❌ {context_name}: Fallback model ALSO failed! Error: {fallback_error}")
                return f"⚠️ Error: LLM completely unavailable for {context_name}."

    def summarize_predictions(self, predictions_data):
        if not self.is_active:
            return "⚠️ LLM Agent is inactive."

        if not predictions_data:
            return "✅ No new predictions to summarize."

        print("🤖 LLM Agent: Translating prediction data into human-readable tactical summary...")

        data_str = json.dumps(predictions_data, ensure_ascii=False, indent=2)

        prompt = f"""
        You are a tactical forecasting analyst for the Fire and Rescue Service.
        Data (JSON): {data_str}

        Task: Analyze the raw fire data and provide a tactical forecast using a clear, human-readable structure.

        RULES:
        1. **Threat Assessment:** Write exactly ONE flowing, natural sentence that explains the actual danger. Focus on the 'So what?' (e.g., is it moving fast? is it threatening buildings?). Avoid robotic, data-dump phrasing.
        2. **Key Metrics:** Extract the raw numbers into a clean bulleted list exactly as shown in the example.
        3. **Vector Format:** Always write the textual cardinal direction first, followed by the numeric degrees in parentheses (e.g., South-East (130°)).
        4. Do NOT include Lat/Lon coordinates in this text.
        5. Return ONLY the Markdown text. No conversational filler.
        6. STRICT METRICS: Limit the 'Key Metrics' list EXACTLY to the 4 items shown in the example (Vector, Wind, Fuel, Intensity). DO NOT add Temperature, Time, or any other metrics.

        EXAMPLE OUTPUT FORMAT:
        **🔥 Threat Assessment:**
        The fire is spreading rapidly eastward into built areas, driven by strong winds, presenting a significant threat to nearby infrastructure.

        **📊 Key Metrics:**
        * 🧭 **Vector:** South-East (130°)
        * 💨 **Wind:** Northwest (7.8 km/h)
        * 🌾 **Fuel:** Built area structures
        * 📏 **Intensity:** Spread: 195 m/h | Flame: 0.98m

        YOUR OUTPUT:
        """

        # שימוש במנגנון ה-Fallback החדש
        return self._call_llm_with_fallback(prompt, context_name="Prediction Summary")

    def summarize_dispatch(self, district_name, dispatch_data):
        """
        מקבלת שם מחוז ואת ה-JSON של שיבוץ הכוחות (כולל שמות התחנות),
        ומחזירה JSON מובנה עם סיכום מחוזי וסיכומים טקטיים לכל שריפה בפורמט Markdown.
        """
        if not self.is_active:
            return '{"error": "LLM Agent is inactive."}'

        if not dispatch_data:
            return '{"district_overview": "No resources were dispatched in this cycle.", "fires_allocation": []}'

        print(f"🤖 LLM Agent: Generating structured dispatch summary for {district_name} district...")

        data_str = json.dumps(dispatch_data, ensure_ascii=False, indent=2)

        prompt = f"""
        You are the Chief AI Dispatcher for a Fire Management Optimization System.
        Data (JSON): {data_str}

        Task: Analyze the dispatch data for the '{district_name}' district and return a STRICT JSON output.

        CRITICAL RULES:
        1. You MUST return ONLY valid JSON. No markdown formatting around the output (like ```json), no conversational text.
        2. DO NOT SKIP ANY FIRE EVENT. You must iterate through the provided data and create an entry in the `fires_allocation` array for EVERY SINGLE FIRE listed.
        3. ROUND Lat/Lon to 3 decimal places in your tactical summaries.
        4. Use Markdown formatting (\n\n for new paragraphs, **bold** for titles, * for bullet points) INSIDE the JSON string values.
        5. The `event_id` in the `fires_allocation` array MUST be an integer (extract the number from keys like "fire_8").
        6. DO NOT include exact coordinates (Lat/Lon) inside the Tactical Assessment paragraph. Focus strictly on the threat analysis and rationale.
        
        FORMATTING RULES:
        - `district_overview`: Provide a "Strategic Focus" (1-2 sentences explaining the logic of the district's resource allocation) followed by a "Unit Distribution" bulleted list mapping events to units.
        - `tactical_summary`: Provide a "Tactical Assessment" (1 sentence explaining the risk/priority of this specific fire) followed by "Dispatch Orders" as a clean bulleted list.

        EXPECTED JSON SCHEMA:
        {{
          "district_name": "{district_name}",
          "district_overview": "**Strategic Focus:**\\nMain effort is prioritized to contain the high-risk fire in the eastern sector, threatening built areas. Secondary fires are being managed with rapid-response units.\\n\\n**Unit Distribution:**\\n* **Event #22:** 1x ROTEM from Beit She'an\\n* **Event #12:** 2x SAAR from Tiberias",
          "fires_allocation": [
            {{
              "event_id": 22,
              "tactical_summary": "**Tactical Assessment:**\\nFire is spreading rapidly towards agricultural infrastructure. Immediate containment is required on the eastern flank.\\n\\n**Dispatch Orders:**\\n* 🚒 **1x ROTEM** | From: Beit She'an | ETA: 22.7 min"
            }},
            {{
              "event_id": 12,
              "tactical_summary": "**Tactical Assessment:**\\nModerate risk fire requiring standard intervention to prevent escalation.\\n\\n**Dispatch Orders:**\\n* 🚒 **2x SAAR** | From: Tiberias | ETA: 15.2 min"
            }}
          ]
        }}

        YOUR JSON OUTPUT:
        """
        
        # שימוש במנגנון ה-Fallback מול Groq
        response_text = self._call_llm_with_fallback(prompt, context_name=f"Dispatch {district_name}")
        
        return response_text
