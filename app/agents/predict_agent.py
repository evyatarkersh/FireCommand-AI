import math
from datetime import datetime
from app.extensions import db
from app.models.fire_events import FireEvent
from app.agents.llm_agent import LLMAgent
from app.extensions import socketio


class FirePredictorAgent:
    def __init__(self):
        self.llm_agent = LLMAgent()

    def run_cycle(self, target_hours=1.0):
        """
        מתעורר (לרוב על ידי סוכן המפקד), סורק את ה-DB לאירועים פעילים, 
        מבצע חישוב של גבולות הגזרה עבור טווח השעות המבוקש ושומר.
        """
        print(f"\n🔮 Predictor Agent: מתעורר ומחשב תחזית ל-{target_hours} שעות קדימה...")

        # שליפת אירועים: כל אירוע פעיל מקבל חיזוי מחדש, גם אם כבר יש לו אחד!
        events_to_predict = FireEvent.query.filter(
            FireEvent.is_active == True
        ).all()

        if not events_to_predict:
            print("   💤 אין אירועים פעילים שדורשים יצירת תחזית כרגע.")
            return

        print(f"   🚀 נמצאו {len(events_to_predict)} אירועים פעילים. מתחיל חישוב...")

        events_updated = 0
        for event in events_to_predict:
            success = self._calculate_and_update(event, target_hours)
            if success:
                events_updated += 1

        # שמירה מרוכזת לכל האירועים שעודכנו
        if events_updated > 0:
            try:
                print("   💾 Predictor: שומר את כל הפוליגונים המעודכנים ל-DB...")
                db.session.commit()
                print("   ✅ תחזיות נשמרו בהצלחה!")
                
                for event in events_to_predict: # תחליף במשתנה שלך שמחזיק את האירועים
                    socketio.emit('prediction_update', {
                        'event_id': event.id,
                        'prediction_polygon': event.prediction_polygon, # וודא שזה השם של שדה ה-GeoJSON שלך
                        'prediction_summary': event.prediction_summary
                    })
                    print("emitted prediction update for event", event.id)
        # נשימה קטנה לשרת כמו שעשינו קודם
                    socketio.sleep(0.05)   
                
            except Exception as e:
                db.session.rollback()
                print(f"   ❌ Predictor Error (Commit Fail): {e}")

    def _calculate_and_update(self, event, target_hours):
        """ חישוב מודל התפשטות האש לאירוע בודד לפי שעות היעד """
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

            # 3. מתמטיקה מכוילת - מודל רות'רמל (ROS) - מחשב קצב מטר/שעה
            effective_wind_kmh = (wind_speed * 0.6 + gust * 0.4) * 3.6
            
            wind_factor = 1.0 + (0.1 * effective_wind_kmh)
            if wind_factor > 4.5:
                wind_factor = 4.5  
            
            solar_factor = 1.2 if 90 < aspect < 270 else 1.0
            dryness = 1.0
            if humidity < 20: dryness += 0.5
            if temp > 30: dryness += 0.3
            total_dryness = dryness * solar_factor

            slope_factor = math.exp(0.069 * slope)
            
            base_ros = fuel_load * 40.0 
            
            # קצבי התפשטות (מטר לשעה)
            ros_head = base_ros * wind_factor * slope_factor * total_dryness
            ros_flank = ros_head * 0.35
            ros_back = ros_head * 0.05

            # 4. חישוב גובה להבה ורמת סיכון
            flame_length = 0.07 * (ros_head ** 0.5)
            risk_level = "MODERATE"
            if flame_length > 3.0: risk_level = "EXTREME"
            elif flame_length > 1.5: risk_level = "HIGH"

            # 5. כיוון האש וגיאומטריה (GeoJSON) - מכפילים בזמן היעד!
            spread_azimuth = (wind_dir + 180) % 360
            
# מנגנון מקדם דעיכת זמן (Time-Decay) כדי למנוע פוליגונים מוגזמים בטווחים ארוכים
            effective_hours = target_hours
            if target_hours > 3.0:
                effective_hours = 3.0 + ((target_hours - 3.0) * 0.5)

            # המרחק האמיתי שהאש תעבור לפי השעות האפקטיביות
            head_distance = ros_head * effective_hours
            back_distance = ros_back * effective_hours
            flank_distance = ros_flank * effective_hours

            polygon = self._generate_ellipse_geojson(
                event.latitude, event.longitude, spread_azimuth, 
                head_distance, back_distance, flank_distance
            )

            # 6. עדכון האובייקט לקראת השמירה
            event.pred_ros = ros_head # שומרים את הקצב לשעה כמידע סטטיסטי
            event.pred_direction = spread_azimuth
            event.pred_flame_length = flame_length
            event.pred_risk_level = risk_level
            event.prediction_polygon = polygon
            event.prediction_updated_at = datetime.utcnow()

            # 7. קריאה ל-LLM Agent
            try:
                prediction_data = self._build_llm_payload(event)
                # נוסיף גם את טווח השעות למידע שה-LLM מקבל
                prediction_data["predictions"]["time_horizon_hours"] = target_hours
                
                readable_prediction = self.llm_agent.summarize_predictions([prediction_data])
                event.prediction_summary = readable_prediction
            except Exception as e:
                print(f"      ⚠️ שגיאת LLM באירוע {event.id}, ממשיך ללא סיכום מילולי. פירוט: {e}")
                event.prediction_summary = "⚠️ תקלה זמנית ביצירת הסיכום המילולי."

            print(f"      ✅ אירוע {event.id}: חיזוי ל-{target_hours} שעות הושלם (ROS={int(ros_head)}m/h, סיכון={risk_level})")
            return True

        except Exception as e:
            print(f"      ⚠️ שגיאה בחישוב לאירוע {event.id}: {e}")
            return False

    # --- פונקציות גיאומטריה נשארות זהות ---
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
        # ... ללא שינוי, בדיוק כמו הקוד המקורי שלך ...
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
                "rate_of_spread_meters_per_hour": getattr(event, 'pred_ros', 0.0),
                "flame_length_meters": getattr(event, 'pred_flame_length', 0.0),
                "spread_direction_azimuth": getattr(event, 'pred_direction', 0.0),
                "risk_level": getattr(event, 'pred_risk_level', 'UNKNOWN'),
                "prediction_timestamp": str(getattr(event, 'prediction_updated_at', ''))
            }
        }

        return payload