import math
from datetime import datetime, timedelta
from app.extensions import db
from app.models.fire_events import FireEvent
from app.models.nasa_fire import FireIncident
from app.agents.open_weather_map_agent import WeatherService
# --- שינוי 1: ייבוא הסוכנים החדשים (היעילים) ---
from app.agents.open_weather_map_agent import WeatherService
from app.agents.topo_agent import enrich_with_topography
from app.agents.IMS_DATA_agent import enrich_with_ims
from app.agents.fuel_agent import enrich_with_fuel


class MonitorAgent:
    def __init__(self):
        self.weather_service = WeatherService()
        self.CLUSTER_RADIUS_KM = 2.5
        self.EVENT_TIMEOUT_HOURS = 24

    def run_cycle(self):
        print("🕵️ Monitor Agent: Starting cycle...")

        # 1. שליפת נתונים גולמיים חדשים
        unprocessed_reads = FireIncident.query.filter_by(is_processed=False).all()

        if not unprocessed_reads:
            print("Monitor: No new raw data.")
            return

        events_to_enrich = set()

        # --- השינוי הגדול: טעינת אירועים לזיכרון לפני הלולאה ---
        cutoff = datetime.utcnow() - timedelta(hours=self.EVENT_TIMEOUT_HOURS)
        # אנחנו שומרים את האירועים ברשימה פייתונית רגילה
        self.active_events_cache = FireEvent.query.filter(FireEvent.last_update >= cutoff).all()

        print(f"Loaded {len(self.active_events_cache)} active events into memory cache.")

        # 2. מעבר על הרשומות ואיחוד (Clustering)
        for read in unprocessed_reads:
            matched_event = self._find_matching_event_in_memory(read)

            if matched_event:
                # -- עדכון אירוע קיים --
                self._update_existing_event(matched_event, read)
                read.event = matched_event
                events_to_enrich.add(matched_event)
                print(f" -> Merged read #{read.id} into Event #{matched_event.id}")
            else:
                # -- יצירת אירוע חדש --
                new_event = self._create_new_event(read)
                db.session.add(new_event)
                db.session.flush()  # כדי לקבל ID

                read.event = new_event
                events_to_enrich.add(new_event)

                # --- קריטי: הוספת האירוע החדש לרשימה שבזיכרון ---
                # כך שבאיטרציה הבאה, המערכת כבר תכיר אותו!
                self.active_events_cache.append(new_event)

                print(f" -> Created NEW Event #{new_event.id} from read #{read.id}")

            # סימון שטופל
            read.is_processed = True

        # שמירת השינויים המבניים (טבלאות)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"❌ Monitor Error (Commit): {e}")
            return

        print(f"🌍 Enriching {len(events_to_enrich)} events with external data...")
        
        for event in events_to_enrich:
            # אנחנו מעבירים את האובייקט עצמו (event) ולא את ה-ID
            
            # א. מזג אוויר
            self.weather_service.update_weather_for_event(event)
            
            # ב. טופוגרפיה
            enrich_with_topography(event)
            
            # ג. נתוני IMS (תחנות)
            enrich_with_ims(event)
            
            # ד. סוג דלק (קרקע)
            enrich_with_fuel(event)

        # --- שינוי 3: שמירה מרוכזת בסוף (Unit of Work) ---
        try:
            print("💾 Committing all changes to DB...")
            db.session.commit()
            print("✅ Monitor cycle finished and saved successfully.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Monitor Error (Critical Commit Fail): {e}")
            return
        # 4. הפעלת Prediction Agent
        self._trigger_prediction_agent(events_to_enrich)

        print("✅ Monitor cycle finished.")

    def _find_matching_event_in_memory(self, read):
        """ מחפש אירוע קרוב מתוך הרשימה שבזיכרון """
        closest, min_dist = None, float('inf')

        # רצים על הרשימה המקומית (active_events_cache) במקום שאילתת SQL
        for event in self.active_events_cache:
            dist = self._calculate_distance(read.latitude, read.longitude, event.latitude, event.longitude)
            if dist < self.CLUSTER_RADIUS_KM:
                if dist < min_dist:
                    min_dist = dist
                    closest = event
        return closest

    def _create_new_event(self, read):
        """ יצירת אירוע חדש עם גבולות ראשוניים """
        return FireEvent(
            latitude=read.latitude,
            longitude=read.longitude,
            # גבולות גזרה התחלתיים (נקודה בודדת)
            min_lat=read.latitude, max_lat=read.latitude,
            min_lon=read.longitude, max_lon=read.longitude,
            # סטטיסטיקות
            brightness=read.brightness,
            frp=read.frp,
            confidence=read.confidence,
            source=read.source,
            detected_at=read.detected_at,
            last_update=read.detected_at,
            num_points=1
        )

    def _update_existing_event(self, event, read):
        """ הרחבת הגבולות ועדכון הסטטיסטיקות """
        # 1. הרחבת גבולות הגזרה (Bounding Box)
        event.min_lat = min(event.min_lat, read.latitude)
        event.max_lat = max(event.max_lat, read.latitude)
        event.min_lon = min(event.min_lon, read.longitude)
        event.max_lon = max(event.max_lon, read.longitude)

        # 2. עדכון המרכז (ממוצע בין הגבולות החדשים)
        event.latitude = (event.min_lat + event.max_lat) / 2
        event.longitude = (event.min_lon + event.max_lon) / 2

        # 3. עדכון עוצמות (שומרים את המקסימום שנצפה באירוע)
        if read.frp > event.frp:
            event.frp = read.frp
        if read.brightness > event.brightness:
            event.brightness = read.brightness

        # 4. עדכון מונים וזמנים
        event.num_points += 1
        event.last_update = datetime.utcnow()

    def _trigger_prediction_agent(self, events):
        """ כאן בעתיד נקרא לסוכן החיזוי """
        if not events: return
        ids = [e.id for e in events]
        print(f"🔮 Triggering Prediction Agent for events: {ids}")
        # prediction_agent.predict(ids)

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        # Haversine implementation
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(
            dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c