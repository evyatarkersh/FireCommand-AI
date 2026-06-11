import math
import os
from datetime import datetime

from flask_socketio import SocketIO

from app.agents.llm_agent import LLMAgent
from app.extensions import db
from app.models.fire_events import FireEvent


class FirePredictorAgent:
    """Agent responsible for predicting fire spread behavior using environmental data and the Rothermel fire spread model, generating prediction polygons for active fire events and broadcasting updates via WebSocket."""

    def __init__(self):
        """Initializes the FirePredictorAgent with an LLM agent for generating human-readable prediction summaries."""
        self.llm_agent = LLMAgent()

    def run_cycle(self, target_hours=1.0):
        """Scans the database for active fire events, calculates fire spread predictions for the specified time horizon using the Rothermel model, updates event records with prediction polygons and risk assessments, and broadcasts results to connected clients via WebSocket."""
        print(f"\n🔮 Predictor Agent: Waking up and calculating prediction for {target_hours} hours ahead...")

        # Query all active fire events that require prediction
        events_to_predict = FireEvent.query.filter(
            FireEvent.is_active == True
        ).all()

        if not events_to_predict:
            print("   💤 No active events requiring prediction at this time.")
            return

        print(f"   🚀 Found {len(events_to_predict)} active events. Starting calculation...")

        events_updated = 0
        for event in events_to_predict:
            success = self._calculate_and_update(event, target_hours)
            if success:
                events_updated += 1

        # Save all updated predictions to the database
        if events_updated > 0:
            try:
                print("   💾 Predictor: Saving all updated polygons to DB...")
                db.session.commit()
                print("   ✅ Predictions saved successfully!")

                # Retrieve Redis URL for distributed WebSocket communication
                redis_url = os.environ.get('REDIS_URL')

                # Create WebSocket emitter with Redis support if available for multi-worker environments
                emitter = SocketIO(message_queue=redis_url) if redis_url else SocketIO()

                for event in events_to_predict:
                    emitter.emit('prediction_update', {
                        'event_id': event.id,
                        'prediction_polygon': event.prediction_polygon,
                        'prediction_summary': event.prediction_summary
                    })
                    print("emitted prediction update for event", event.id)
                    # Introduce a brief delay to prevent overwhelming the server
                    emitter.sleep(1)

            except Exception as e:
                db.session.rollback()
                print(f"   ❌ Predictor Error (Commit Fail): {e}")

    def _calculate_and_update(self, event, target_hours):
        """Calculates fire spread predictions for a single event using the Rothermel model with environmental data, applies time-decay for long-range forecasts, and updates the event with prediction polygon, risk level, and LLM-generated summary text."""
        try:
            # Retrieve environmental data with IMS as priority and OWM as fallback
            wind_speed = event.ims_wind_speed if (event.ims_wind_speed is not None and event.ims_wind_speed >= 0) else (event.owm_wind_speed or 0)
            wind_dir = event.ims_wind_dir if (event.ims_wind_dir is not None and event.ims_wind_dir >= 0) else (event.owm_wind_deg or 0)
            temp = event.ims_temp if (event.ims_temp is not None and event.ims_temp > -100) else (event.owm_temperature or 25)
            humidity = event.ims_humidity if (event.ims_humidity is not None and event.ims_humidity >= 0) else (event.owm_humidity or 50)

            rain = event.ims_rain or 0.0
            gust = event.ims_wind_gust or wind_speed
            fuel_load = event.fuel_load or 1.0
            slope = event.topo_slope or 0
            aspect = event.topo_aspect or 0

            # If rain is detected, halt fire spread calculation and set minimal polygon
            if rain > 0.5:
                print(f"      🌧️ Event {event.id}: Rain detected. Setting point polygon.")
                event.pred_ros = 0
                event.pred_risk_level = "LOW"
                event.pred_direction = 0
                event.pred_flame_length = 0
                event.prediction_polygon = self._generate_point_geojson(event.latitude, event.longitude)
                event.prediction_updated_at = datetime.utcnow()
                return True

            # Apply calibrated Rothermel model to calculate rate of spread in meters per hour
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

            # Calculate spread rates in meters per hour for head, flank, and back of fire
            ros_head = base_ros * wind_factor * slope_factor * total_dryness
            ros_flank = ros_head * 0.35
            ros_back = ros_head * 0.05

            # Determine flame length and classify risk level based on fire intensity
            flame_length = 0.07 * (ros_head ** 0.5)
            risk_level = "MODERATE"
            if flame_length > 3.0:
                risk_level = "EXTREME"
            elif flame_length > 1.5:
                risk_level = "HIGH"

            # Calculate fire spread direction and generate prediction geometry as GeoJSON
            spread_azimuth = (wind_dir + 180) % 360

            # Apply time-decay mechanism to prevent exaggerated polygons for long-term predictions
            effective_hours = target_hours
            if target_hours > 3.0:
                effective_hours = 3.0 + ((target_hours - 3.0) * 0.5)

            # Calculate distances the fire will travel in each direction based on effective time
            head_distance = ros_head * effective_hours
            back_distance = ros_back * effective_hours
            flank_distance = ros_flank * effective_hours

            polygon = self._generate_ellipse_geojson(
                event.latitude, event.longitude, spread_azimuth,
                head_distance, back_distance, flank_distance
            )

            # Update event object with calculated prediction data
            event.pred_ros = ros_head
            event.pred_direction = spread_azimuth
            event.pred_flame_length = flame_length
            event.pred_risk_level = risk_level
            event.prediction_polygon = polygon
            event.prediction_updated_at = datetime.utcnow()

            # Generate human-readable prediction summary using LLM agent
            try:
                prediction_data = self._build_llm_payload(event)
                prediction_data["predictions"]["time_horizon_hours"] = target_hours

                readable_prediction = self.llm_agent.summarize_predictions([prediction_data])
                event.prediction_summary = readable_prediction
            except Exception as e:
                print(f"      ⚠️ LLM error for event {event.id}, continuing without text summary. Details: {e}")
                event.prediction_summary = "⚠️ Temporary issue generating text summary."

            print(
                f"      ✅ Event {event.id}: Prediction for {target_hours} hours completed (ROS={int(ros_head)}m/h, Risk={risk_level})")
            return True

        except Exception as e:
            print(f"      ⚠️ Calculation error for event {event.id}: {e}")
            return False

    def _generate_ellipse_geojson(self, lat, lon, azimuth, head_m, back_m, flank_m):
        """Generates an elliptical polygon in GeoJSON format representing the predicted fire spread area, calculated from the origin coordinates, spread direction azimuth, and distances traveled in head, back, and flank directions."""
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

            # Rotate point coordinates by azimuth angle
            rot_x = x * math.cos(-azimuth_rad) - y * math.sin(-azimuth_rad)
            rot_y = x * math.sin(-azimuth_rad) + y * math.cos(-azimuth_rad)

            final_x = offset_x + rot_x
            final_y = offset_y + rot_y

            # Convert from meters to degrees for geographic coordinates
            delta_lat = final_y / 111000.0
            delta_lon = final_x / (111000.0 * math.cos(math.radians(lat)))

            points.append([lon + delta_lon, lat + delta_lat])

        # Close the polygon by repeating the first point
        points.append(points[0])
        return {"type": "Polygon", "coordinates": [points]}

    def _generate_point_geojson(self, lat, lon):
        """Creates a minimal point-based polygon in GeoJSON format for fire events where no spread is expected, such as when rain is detected."""
        return {"type": "Polygon", "coordinates": [[[lon, lat], [lon, lat], [lon, lat], [lon, lat]]]}

    def _build_llm_payload(self, event):
        """Constructs a structured payload dictionary containing fire event data, environmental conditions, and prediction results for LLM processing and summary generation."""
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
