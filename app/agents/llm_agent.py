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

        print("🤖 LLM Agent: Translating prediction data into human-readable summary...")

        data_str = json.dumps(predictions_data, ensure_ascii=False, indent=2)

        prompt = f"""
        You are a tactical forecasting analyst for the Fire and Rescue Service.
        Data (JSON): {data_str}

        Task: Translate the JSON into a strict, highly concise 2-line briefing.

        RULES:
        1. ROUND Lat/Lon to 3 decimal places.
        2. MAX 2 sentences for the forecast. NO fluff, NO filler words.
        3. Follow the exact style of the Example Output.

        EXAMPLE OUTPUT FORMAT:
        📍 **Location & Risk:** Lat 31.844, Lon 34.678 | Risk: MODERATE
        🔥 **Forecast:** Fire spreading at 130° (South-East) at 195 m/h, fueled by built area structures. Flame lengths of 0.98m are driven by northwest winds at 7.8 km/h.

        YOUR OUTPUT (Analyze the JSON and use the exact format above):
        """

        # שימוש במנגנון ה-Fallback החדש
        return self._call_llm_with_fallback(prompt, context_name="Prediction Summary")

    def summarize_dispatch(self, district_name, dispatch_data):
        """
        מקבלת שם מחוז ואת ה-JSON של שיבוץ הכוחות,
        ומחזירה דיווח מבצעי אנושי המיועד למפקד הזירה.
        """
        if not self.is_active:
            return "⚠️ LLM Agent is inactive."

        if not dispatch_data:
            return "✅ No resources were dispatched in this cycle."

        print(f"🤖 LLM Agent: Generating operational dispatch summary for {district_name} district...")

        data_str = json.dumps(dispatch_data, ensure_ascii=False, indent=2)

        prompt = f"""
        You are the Chief AI Dispatcher. 
        Data (JSON): {data_str}

        Task: Provide a structured recommendation for the '{district_name}' district.

        RULES:
        1. ROUND Lat/Lon to 3 decimal places.
        2. The Strategy section MUST be EXACTLY ONE sentence. NO generic advice, NO fluff.
        3. STRICTLY PROHIBITED: Do not write raw JSON keys like "eta_minutes", "lat", "lon", or "status" in the Strategy paragraph. Speak naturally.
        4. Ignore the "status" field for the narrative (e.g., do not say "resolved fires").
        5. You MUST include a double line break (blank line) immediately after the District header.
        6. Follow the exact style of the Example Output.

        EXAMPLE OUTPUT FORMAT:
        👨‍✈️ **Dispatch Strategy: {district_name} District**

        Main effort is focused on fire_4 with heavy SAAR units, while fire_3 receives a single ROTEM for rapid response.

        **Recommended Deployment:**
        * **fire_4** (Lat 31.844, Lon 34.678): Allocate 1x SAAR (ETA: 13.5 min) and 1x ROTEM (ETA: 13.5 min).
        * **fire_3** (Lat 31.343, Lon 34.443): Allocate 1x ROTEM (ETA: 10.5 min).

        YOUR OUTPUT (Analyze the JSON and use the exact format above):
        """
        
        # שימוש במנגנון ה-Fallback החדש
        return self._call_llm_with_fallback(prompt, context_name=f"Dispatch {district_name}")