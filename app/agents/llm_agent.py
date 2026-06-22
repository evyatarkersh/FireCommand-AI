import json
import os

import google.generativeai as genai
from groq import Groq
from groq.types.chat import ChatCompletionUserMessageParam
from openai import OpenAI


class LLMAgent:
    """
    Manages Large Language Model API interactions with automatic failover between Groq and Gemini services for generating tactical fire management summaries and dispatch recommendations.
    """

    def __init__(self):
        """
        Initializes the LLM Agent by loading multiple Groq API keys and configuring Gemini as a fallback, ensuring high availability for critical fire management operations.
        """
        # 1. Initialize OpenRouter (Primary Model)
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        if self.openrouter_key:
            self.openrouter_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_key,
            )
        else:
            self.openrouter_client = None

        # 2. Initialize Groq (First Fallback)
        self.groq_keys = [
            os.getenv("GROQ_API_KEY"),
            os.getenv("GROQ_API_KEY_1")
        ]
        self.groq_keys = [k for k in self.groq_keys if k]

        # 3. Initialize Gemini (Final Fallback)
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            self.gemini_model = genai.GenerativeModel('gemini-3.1-flash-lite')
        else:
            self.gemini_model = None

        self.is_active = self.openrouter_key is not None or len(self.groq_keys) > 0 or self.gemini_key is not None
        if not self.is_active:
            print("❌ LLM Agent Error: No API keys found for OpenRouter, Groq, or Gemini.")

    def _call_llm_with_fallback(self, prompt, context_name="LLM", is_json=False):
        """
        Attempts to execute a prompt across multiple Groq API keys using high-capacity models, falling back to Gemini if all Groq attempts fail, and returns the generated text response or error message.
        """
        # Step 1: Try OpenRouter (Primary)
        if self.openrouter_client:
            fallback_models = [
                "openrouter/auto-large:free", "openrouter/auto:free"
            ]
            or_kwargs = {"temperature": 0.1}
            if is_json:
                or_kwargs["response_format"] = {"type": "json_object"}

            for model_name in fallback_models:
                try:
                    print(f"      🔄 {context_name}: Trying OpenRouter ({model_name})...")
                    response = self.openrouter_client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        **or_kwargs
                    )
                    print(f"      🟢 {context_name}: Success using OpenRouter")
                    return response.choices[0].message.content
                except Exception as e:
                    print(f"      ⚠️ {context_name}: Error with OpenRouter {model_name}: {e}")
                    if is_json and "response_format" in str(e):
                        try:
                            print(f"      🔄 {context_name}: Retrying without strict JSON mode...")
                            response = self.openrouter_client.chat.completions.create(
                                model=model_name,
                                messages=[{"role": "user", "content": prompt}],
                                temperature=0.1
                            )
                            return response.choices[0].message.content
                        except:
                            pass
                    continue

        # Step 2: Try Groq (First Fallback)
        if self.groq_keys:
            print(f"      🚨 {context_name}: OpenRouter exhausted. Trying Groq...")
            groq_strong_models = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b"]
            kwargs = {"temperature": 0.1}
            if is_json:
                kwargs["response_format"] = {"type": "json_object"}

            for key_index, api_key in enumerate(self.groq_keys):
                client = Groq(api_key=api_key)
                for model_name in groq_strong_models:
                    try:
                        print(f"      🔄 {context_name}: Trying Groq Key #{key_index + 1} ({model_name})...")
                        chat_completion = client.chat.completions.create(
                            messages=[ChatCompletionUserMessageParam(role="user", content=prompt)],
                            model=model_name,
                            **kwargs
                        )
                        print(f"      🟢 {context_name}: Success using Groq")
                        return chat_completion.choices[0].message.content
                    except Exception as e:
                        print(f"      ⚠️ {context_name}: Error with Groq {model_name}: {e}")
                        continue

        # Step 3: Try Gemini (Final Fallback)
        if self.gemini_model:
            try:
                print(f"      🚨 {context_name}: Groq exhausted. Trying Gemini...")
                generation_config = {"temperature": 0.1}
                if is_json:
                    generation_config["response_mime_type"] = "application/json"

                response = self.gemini_model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                print(f"      🟢 {context_name}: Success using Gemini")
                return response.text
            except Exception as e:
                print(f"      ❌ {context_name}: Gemini fallback failed: {e}")

        # Step 4: Everything failed
        error_text = f"⚠️ Error: LLM completely unavailable for {context_name}."
        print(error_text)
        return '{"error": "API Blocked"}' if is_json else error_text

    def summarize_predictions(self, predictions_data):
        """
        Converts raw fire prediction data into a structured, human-readable tactical forecast with threat assessment and key metrics in Markdown format, returning a summary string or error/status message.
        """
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
        7. **Time Horizon Context:** Locate the 'time_horizon_hours' value in the JSON data. You MUST include this timeframe explicitly in both the title of the Threat Assessment and within its sentence (e.g., "Over the next X hours...")
        
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

        return self._call_llm_with_fallback(prompt, context_name="Prediction Summary")

    def summarize_dispatch(self, district_name, dispatch_data):
        """
        Generates structured JSON output containing district-level resource allocation overview and individual tactical summaries for each fire event, formatted with Markdown text for presentation, or returns an error message if the agent is inactive or data is empty.
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

        # Use the fallback mechanism with Groq
        response_text = self._call_llm_with_fallback(prompt, context_name=f"Dispatch {district_name}", is_json=True)

        return response_text
