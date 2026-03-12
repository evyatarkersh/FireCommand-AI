import math
from datetime import datetime
from app.extensions import db
from app.models.fire_events import FireEvent
from app.agents.llm_agent import LLMAgent

class FirePredictorAgent:
    def __init__(self):
        self.llm_agent = LLMAgent()

    def run_cycle(self):
        """
        מתעורר, סורק את ה-DB לאירועים שדורשים חיזוי, מבצע חישוב ושומר.
        לא מקבל שום פרמטר חיצוני.
        """
        print("\n🔮 Predictor Agent: מתעורר וסורק את מסד הנתונים...")

        # שליפת אירועים: פעילים, שאין להם פוליגון או שאין להם חותמת זמן
        events_to_predict = FireEvent.query.filter(
            FireEvent.is_active == True,
            (FireEvent.prediction_polygon.is_(None)) | 
            (FireEvent.prediction_updated_at.is_(None))
        ).all()

        if not events_to_predict:
            print("   💤 אין אירועים שדורשים יצירת תחזית כרגע.")
            return

        print(f"   🚀 נמצאו {len(events_to_predict)} אירועים ללא תחזית. מתחיל חישוב...")

        events_updated = 0
        for event in events_to_predict:
            success = self._calculate_and_update(event)
            if success:
                events_updated += 1

        # שמירה מרוכזת לכל האירועים שעודכנו
        if events_updated > 0:
            try:
                print("   💾 Predictor: שומר את כל הפוליגונים החדשים ל-DB...")
                db.session.commit()
                print("   ✅ תחזיות נשמרו בהצלחה!")
            except Exception as e:
                db.session.rollback()
                print(f"   ❌ Predictor Error (Commit Fail): {e}")

    def _calculate_and_update(self, event):
        """ חישוב מודל התפשטות האש לאירוע בודד """
        try:
            # 1. שליפת נתונים (עדיפות ל-IMS, גיבוי OWM)
            wind_speed = event.ims_wind_speed if event.ims_wind_speed is not None else (event.owm_wind_speed or 0)
            wind_dir = event.ims_wind_dir if event.ims_wind_dir is not None else (event.owm_wind_deg or 0)
            temp = event.ims_temp if event.ims_temp is not None else (event.owm_temperature or 25)
            humidity = event.ims_humidity if event.ims_humidity is not None else (event.owm_humidity or 50)
            
            rain = event.ims_rain or 0.0
            gust = event.ims_wind_gust or wind_speed
            fuel_load = event.fuel_load or 1.0
            slope = event.topo_slope or 0
            aspect = event.topo_aspect or 0

            # 2. עצירה עקב גשם
            if rain > 0.5:
                print(f"      🌧️ אירוע {event.id}: זוהה גשם. מקבע פוליגון נקודתי.")
                event.pred_ros = 0
                event.pred_risk_level = "LOW"
                event.pred_direction = 0
                event.pred_flame_length = 0
                event.prediction_polygon = self._generate_point_geojson(event.latitude, event.longitude)
                event.prediction_updated_at = datetime.utcnow()
                return True

            # 3. מתמטיקה מכוילת - מודל רות'רמל (ROS)
            effective_wind_kmh = (wind_speed * 0.6 + gust * 0.4) * 3.6
            
            # ריסון פקטור הרוח (Cap)
            wind_factor = 1.0 + (0.1 * effective_wind_kmh)
            if wind_factor > 4.5:
                wind_factor = 4.5  
            
            solar_factor = 1.2 if 90 < aspect < 270 else 1.0
            dryness = 1.0
            if humidity < 20: dryness += 0.5
            if temp > 30: dryness += 0.3
            total_dryness = dryness * solar_factor

            slope_factor = math.exp(0.069 * slope)
            
            # בסיס מתון לדלק
            base_ros = fuel_load * 40.0 
            
            # קצבי התפשטות (עם Flank רחב של 35%)
            ros_head = base_ros * wind_factor * slope_factor * total_dryness
            ros_flank = ros_head * 0.35
            ros_back = ros_head * 0.05

            # 4. חישוב גובה להבה ורמת סיכון
            flame_length = 0.07 * (ros_head ** 0.5)
            risk_level = "MODERATE"
            if flame_length > 3.0: risk_level = "EXTREME"
            elif flame_length > 1.5: risk_level = "HIGH"

            # 5. כיוון האש וגיאומטריה (GeoJSON) - נשאר לשעה אחת קדימה
            spread_azimuth = (wind_dir + 180) % 360
            polygon = self._generate_ellipse_geojson(
                event.latitude, event.longitude, spread_azimuth, ros_head, ros_back, ros_flank
            )

            # 6. עדכון האובייקט לקראת השמירה
            event.pred_ros = ros_head
            event.pred_direction = spread_azimuth
            event.pred_flame_length = flame_length
            event.pred_risk_level = risk_level
            event.prediction_polygon = polygon
            event.prediction_updated_at = datetime.utcnow()

            # 7. קריאה ל-LLM Agent על בסיס הנתונים המעודכנים באובייקט
            # עטוף ב-try/except כדי ששגיאת רשת לא תבטל את כל החישוב המתמטי
            try:
                # מניח שיצרת מופע של llm_agent ב- __init__ של המחלקה
                # למשל: self.llm = LLMAgent()

                prediction_data = self._build_llm_payload(event)
                readable_prediction = self.llm_agent.summarize_predictions([prediction_data])

                # העמודה ששומרת את הסיכום למשתמש
                event.prediction_summary = readable_prediction
            except Exception as e:
                print(f"      ⚠️ שגיאת LLM באירוע {event.id}, ממשיך ללא סיכום מילולי. פירוט: {e}")
                event.prediction_summary = "⚠️ תקלה זמנית ביצירת הסיכום המילולי."

            print(f"      ✅ אירוע {event.id}: חיזוי הושלם (ROS={int(ros_head)}m/h, סיכון={risk_level})")
            return True

        except Exception as e:
            print(f"      ⚠️ שגיאה בחישוב לאירוע {event.id}: {e}")
            return False

    # --- פונקציות גיאומטריה ---
    def _generate_ellipse_geojson(self, lat, lon, azimuth, head_m, back_m, flank_m):
        major_axis = (head_m + back_m) / 2.0
        minor_axis = flank_m
        center_offset = (head_m - back_m) / 2.0
        azimuth_rad = math.radians(azimuth)

        offset_y = center_offset * math.cos(azimuth_rad)
        offset_x = center_offset * math.sin(azimuth_rad)

        points = []
        num_points = 16 
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            x = minor_axis * math.cos(angle)
            y = major_axis * math.sin(angle)
            
            rot_x = x * math.cos(-azimuth_rad) - y * math.sin(-azimuth_rad)
            rot_y = x * math.sin(-azimuth_rad) + y * math.cos(-azimuth_rad)
            
            final_x = offset_x + rot_x
            final_y = offset_y + rot_y
            
            delta_lat = final_y / 111000.0
            delta_lon = final_x / (111000.0 * math.cos(math.radians(lat)))
            
            points.append([lon + delta_lon, lat + delta_lat])

        points.append(points[0]) 
        return {"type": "Polygon", "coordinates": [points]}

    def _generate_point_geojson(self, lat, lon):
        return {"type": "Polygon", "coordinates": [[[lon, lat], [lon, lat], [lon, lat], [lon, lat]]]}

    def _build_llm_payload(self, event):
        """
        אורז את הנתונים הרלוונטיים מתוך אובייקט האירוע למילון (JSON-like) עבור סוכן ה-LLM.
        הפונקציה מסננת החוצה מידע כבד כמו הפוליגון, ושולחת רק מה שדרוש לסיכום המילולי.
        """
        # תיעדוף נתוני מזג אוויר (IMS קודם, OWM כגיבוי)
        wind_speed = event.ims_wind_speed if event.ims_wind_speed is not None else (event.owm_wind_speed or 0)
        wind_dir = event.ims_wind_dir if event.ims_wind_dir is not None else (event.owm_wind_deg or 0)
        temp = event.ims_temp if event.ims_temp is not None else (event.owm_temperature or 25)

        payload = {
            "event_id": event.id,
            "location": f"Lat {event.latitude}, Lon {event.longitude}",
            "environment": {
                "fuel_type": getattr(event, 'fuel_type', 'Unknown'),
                "wind_speed_kmh": wind_speed,
                "wind_direction_deg": wind_dir,
                "temperature_c": temp
            },
            "predictions": {
                # השדות האלו בדיוק חושבו ועודכנו באובייקט לפני הקריאה לפונקציה הזו
                "rate_of_spread_meters_per_hour": getattr(event, 'pred_ros', 0.0),
                "flame_length_meters": getattr(event, 'pred_flame_length', 0.0),
                "spread_direction_azimuth": getattr(event, 'pred_direction', 0.0),
                "risk_level": getattr(event, 'pred_risk_level', 'UNKNOWN'),
                "prediction_timestamp": str(getattr(event, 'prediction_updated_at', ''))
            }
        }

        return payload