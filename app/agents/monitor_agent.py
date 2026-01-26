import math
from datetime import datetime, timedelta
from app.extensions import db
# וודא שהשמות תואמים לשמות הקבצים שלך
from app.models.fire_events import FireEvent
from app.models.nasa_fire import FireIncident
from app.agents.open_weather_map_agent import WeatherService


class MonitorAgent:
    def __init__(self):
        self.weather_service = WeatherService()
        # רדיוס בקילומטרים כדי להחשיב נקודה כשייכת לאותו אירוע
        self.CLUSTER_RADIUS_KM = 5.0
        # זמן מקסימלי (בשעות) כדי להחשיב אירוע כ"פעיל" לצורך שיוך
        self.EVENT_TIMEOUT_HOURS = 24

    def run_cycle(self):
        """
        הלולאה הראשית של הסוכן:
        1. שולף נתונים גולמיים חדשים.
        2. משייך לאירועים קיימים או יוצר חדשים.
        3. מפעיל את סוכן מזג האוויר.
        """
        # 1. שליפת רשומות נאס"א שעוד לא טופלו
        unprocessed_reads = FireIncident.query.filter_by(is_processed=False).all()

        if not unprocessed_reads:
            print("Monitor: No new raw data found.")
            return

        print(f"Monitor: Processing {len(unprocessed_reads)} new raw reports...")

        events_to_update_weather = set()  # נשתמש ב-Set כדי לא לעדכן את אותו אירוע פעמיים באותה ריצה

        for read in unprocessed_reads:
            # שלב א: נסה למצוא אירוע קיים שמתאים לדיווח הזה
            matched_event = self._find_matching_event(read)

            if matched_event:
                # מצאנו אירוע קרוב! נעדכן אותו
                print(f" -> Linked read #{read.id} to Existing Event #{matched_event.id}")
                self._update_event_center(matched_event, read)
                read.event = matched_event  # קישור ב-DB (ה-Foreign Key)
                events_to_update_weather.add(matched_event)
            else:
                # לא מצאנו? ניצור אירוע חדש
                print(f" -> Creating NEW Event for read #{read.id}")
                new_event = self._create_new_event(read)

                # טריק חשוב: אנחנו מוסיפים ל-Session אבל עושים Flush
                # כדי לקבל ID עוד לפני ה-Commit הסופי
                db.session.add(new_event)
                db.session.flush()

                read.event = new_event
                events_to_update_weather.add(new_event)

            # סימון שהשורה טופלה
            read.is_processed = True

        # שמירת כל השינויים (יצירת אירועים וקישורים) בדאטה-בייס
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Critical Error in Monitor Commit: {e}")
            return

        # שלב ב: העשרת מזג אוויר (קוראים לזה רק אחרי שיש ID לאירועים)
        print(f"Monitor: Fetching weather for {len(events_to_update_weather)} events...")
        for event in events_to_update_weather:
            self.weather_service.update_weather_for_event(
                event_id=event.id,
                lat=event.latitude,
                lon=event.longitude
            )

        # שלב ג: (בעתיד) כאן נקרא ל-Prediction Agent
        # self.prediction_agent.predict(events_to_update_weather)

    def _find_matching_event(self, read):
        """
        מחפש האם קיים אירוע פעיל בטווח הקילומטרים שהגדרנו.
        הערה: בסיסטם ענק היינו משתמשים ב-PostGIS, אבל לפייתון פשוט זה מספיק.
        """
        # אופטימיזציה: שולפים רק אירועים מהיממה האחרונה
        cutoff_time = datetime.utcnow() - timedelta(hours=self.EVENT_TIMEOUT_HOURS)
        active_events = FireEvent.query.filter(FireEvent.last_update >= cutoff_time).all()

        closest_event = None
        min_dist = float('inf')

        for event in active_events:
            dist = self._calculate_distance(read.latitude, read.longitude, event.latitude, event.longitude)

            if dist < self.CLUSTER_RADIUS_KM:
                # מצאנו משהו בטווח. נבדוק אם הוא הכי קרוב שמצאנו עד כה
                if dist < min_dist:
                    min_dist = dist
                    closest_event = event

        return closest_event

    def _create_new_event(self, read):
        """ יוצר אובייקט אירוע חדש על בסיס הקריאה הגולמית """
        return FireEvent(
            latitude=read.latitude,
            longitude=read.longitude,
            brightness=read.brightness,  # לוקחים נתונים ראשוניים
            frp=read.frp,
            confidence=read.confidence,
            source=read.source,
            detected_at=read.detected_at,
            # שדות ניהול שלנו
            created_at=datetime.utcnow(),
            # last_update לא קיים במודל שלך כרגע, מומלץ להוסיף אותו למודל FireEvent!
            # אם לא תוסיף, תשתמש ב-detected_at לצורך הסינון
        )

    def _update_event_center(self, event, read):
        """ עדכון המיקום של האירוע (ממוצע פשוט) """
        # אפשר לשכלל לממוצע משוקלל, כרגע נעשה ממוצע פשוט כדי להזיז את המרכז לכיוון האש החדשה
        event.latitude = (event.latitude + read.latitude) / 2
        event.longitude = (event.longitude + read.longitude) / 2

        # עדכון נתונים נוספים אם הקריאה החדשה חזקה יותר
        if read.frp > event.frp:
            event.frp = read.frp
            event.brightness = read.brightness

        # עדכון זמן אחרון
        event.detected_at = read.detected_at

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """ נוסחת Haversine לחישוב מרחק בקילומטרים """
        R = 6371.0  # רדיוס כדור הארץ בק"מ

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = math.sin(dlat / 2) ** 2 + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dlon / 2) ** 2

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c