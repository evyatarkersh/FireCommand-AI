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
        You are a seasoned Incident Commander in the Fire and Rescue Service. 
        You are provided with real-time prediction data for active wildfires.

        Data (JSON):
        {data_str}

        Task:
        Provide a highly concise, tactical Situation Report (SitRep).

        STRICT FORMATTING RULES:
        1. DO NOT write any introductory or concluding sentences (e.g., NO "Here is the SitRep...").
        2. DO NOT use nested bullet points.
        3. DO NOT leave empty lines (double line breaks) between bullets.
        4. Use EXACTLY this format for the output:

        **SitRep | Risk: [MODERATE/HIGH/EXTREME]**
        * **Behavior:** Spreading [Compass Direction] at [ROS] m/h.
        * **Tactical:** Flame length [Length]m. [Brief 3-5 word tactical meaning, e.g., "Direct attack dangerous"].
        * **Drivers:** Fueled by [Fuel Type] with wind effects.

        Keep it strictly to the facts provided. Do not invent metrics.
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
        You are the Chief Dispatcher for the Fire and Rescue Service.
        Write a tactical dispatch summary for the '{district_name}' district based ONLY on this JSON:
        {data_str}

        STRICT FORMATTING RULES:
        1. DO NOT write any introductory or concluding sentences (e.g., strictly NO "The following fires...", NO "Please note...").
        2. Start directly with the header on the first line: **🚒 Dispatch Summary: {district_name} District**
        3. For each fire, use exactly ONE bullet point formatted EXACTLY like this:
           * **Event [ID]** ([Lat], [Lon]): [Number]x [Type] units (ETA: [Time] min).
        4. If an ESHED is dispatched, append it to the same line: " + ESHED assigned". 
        5. If no ESHED is dispatched, DO NOT mention it at all.
        6. DO NOT add double line breaks (empty lines) between bullet points.

        Output ONLY the requested markdown text and nothing else.
        """
        
        # שימוש במנגנון ה-Fallback החדש
        return self._call_llm_with_fallback(prompt, context_name=f"Dispatch {district_name}")