import pytest
from app.agents.monitor_agent import MonitorAgent


class MockFireIncident:
    """
    חיקוי (Mock) פשוט ומהיר לרשומה גולמית של נאסא.
    מונע מאיתנו את הצורך לגעת בטבלאות ה-DB האמיתיות במהלך בדיקת היחידה.
    """

    def __init__(self, id, lat, lon, brightness, frp):
        self.id = id
        self.latitude = lat
        self.longitude = lon
        self.brightness = brightness
        self.frp = frp
        self.confidence = 100
        self.source = "VIIRS"
        self.detected_at = "2026-04-20T10:00:00Z"
        self.is_processed = False


def test_monitor_clustering_logic():
    """
    בדיקת אלגוריתם איחוד השריפות (Clustering)
    מוודא ששתי נקודות קרובות מתאחדות, שהמרכז הגיאוגרפי מחושב מחדש,
    ושסטטיסטיקת העוצמה (FRP) לוקחת את המקסימום כפי שהוגדר בקוד.
    """
    monitor = MonitorAgent()

    # מאתחלים את קאש הזיכרון להיות ריק (כמו שהוא יהיה בתחילת ריצה על DB ריק)
    monitor.active_events_cache = []

    # 1. נייצר 3 תצפיות "נאסא" (2 קרובות בירושלים, 1 רחוקה בחיפה)
    # המרחק בין התצפיות בירושלים הוא בערך 1 ק"מ (הרבה מתחת לסף ה-2.5)
    read1 = MockFireIncident(id=1, lat=31.768, lon=35.213, brightness=310.0, frp=25.0)
    read2 = MockFireIncident(id=2, lat=31.775, lon=35.220, brightness=315.0, frp=30.0)

    # חיפה - רחוקה מאוד
    read3 = MockFireIncident(id=3, lat=32.794, lon=34.989, brightness=305.0, frp=20.0)

    raw_reads = [read1, read2, read3]

    # 2. נריץ את לולאת הלוגיקה המרכזית שלך (ללא השמירה ל-DB)
    for read in raw_reads:
        matched_event = monitor._find_matching_event_in_memory(read)

        if matched_event:
            # מצאנו אירוע קרוב -> האלגוריתם שלך מעדכן ומרחיב אותו
            monitor._update_existing_event(matched_event, read)
        else:
            # לא מצאנו -> יצירת חדש והוספה לקאש
            new_event = monitor._create_new_event(read)
            monitor.active_events_cache.append(new_event)

    # 3. מבחני התוצאה (Assertions)

    # בדיקה א': כמות האירועים
    assert len(monitor.active_events_cache) == 2, "האלגוריתם לא איחד את הנקודות הקרובות ויצר יותר מדי אירועים!"

    # נשלוף את האירוע המאוחד (ירושלים היא הדרומית מבין השתיים)
    jerusalem_event = next(e for e in monitor.active_events_cache if e.latitude < 32.0)
    haifa_event = next(e for e in monitor.active_events_cache if e.latitude > 32.0)

    # בדיקה ב': לוגיקת האיחוד (Update Logic)
    assert jerusalem_event.num_points == 2, "מונה הנקודות לא התעדכן בתוך האירוע המאוחד!"
    assert jerusalem_event.frp == 30.0, "ה-FRP של אירוע מאוחד צריך להיות הגבוה מבין השניים (30.0) ולא הסכום!"

    # בדיקה ג': חישוב מחדש של המרכז הגיאוגרפי (Bounding Box center)
    expected_lat_center = (31.768 + 31.775) / 2
    expected_lon_center = (35.213 + 35.220) / 2
    assert jerusalem_event.latitude == expected_lat_center, "קו הרוחב המרכזי לא חושב כממוצע הגבולות!"
    assert jerusalem_event.longitude == expected_lon_center, "קו האורך המרכזי לא חושב כממוצע הגבולות!"

    # בדיקה ד': האירוע המבודד נשאר שלם
    assert haifa_event.num_points == 1
    assert haifa_event.frp == 20.0


from datetime import datetime, timedelta
from app.models.fire_events import FireEvent
from app.extensions import db


def test_monitor_timeout_logic(app):
    """
    מבחן שריפות רפאים (Timeout):
    מוודא שה-Monitor Agent מתעלם משריפות ישנות (מעל 24 שעות)
    ופותח אירוע חדש במקום לאחד נקודות חדשות אל תוך אירוע היסטורי.
    """
    # 1. יצירת שני אירועים היסטוריים ב-DB המזויף שלנו
    with app.app_context():
        now = datetime.utcnow()

        # אירוע טרי (מלפני שעתיים) - פעיל!
        fresh_event = FireEvent(
            id=101, latitude=32.0, longitude=35.0,
            min_lat=32.0, max_lat=32.0, min_lon=35.0, max_lon=35.0,
            detected_at=now - timedelta(hours=2),
            last_update=now - timedelta(hours=2),  # <--- עודכן לפני שעתיים
            num_points=1
        )

        # אירוע ישן (מלפני יומיים) - סגור!
        old_event = FireEvent(
            id=102, latitude=31.0, longitude=34.0,
            min_lat=31.0, max_lat=31.0, min_lon=34.0, max_lon=34.0,
            detected_at=now - timedelta(hours=48),
            last_update=now - timedelta(hours=48),  # <--- פג תוקף!
            num_points=5
        )

        db.session.add(fresh_event)
        db.session.add(old_event)
        db.session.commit()

        # 2. נפעיל את תהליך הטעינה של סוכן הניטור
        monitor = MonitorAgent()

        # אנחנו מדמים את החלק הראשון של פונקציית run_cycle
        cutoff = datetime.utcnow() - timedelta(hours=monitor.EVENT_TIMEOUT_HOURS)
        monitor.active_events_cache = FireEvent.query.filter(FireEvent.last_update >= cutoff).all()

        # 3. מבחני התוצאה (Assertions)
        cached_ids = [event.id for event in monitor.active_events_cache]

        # מוודאים שרק האירוע הטרי נטען לזיכרון
        assert 101 in cached_ids, "האירוע הטרי לא נטען לזיכרון!"
        assert 102 not in cached_ids, "סכנה: ה-Monitor טען אירוע מלפני יומיים! עלול לגרום להקפצת שווא."
        assert len(monitor.active_events_cache) == 1, "נטענו יותר מדי אירועים לזיכרון."


def test_bounding_box_expansion_logic():
    """
    בדיקת יחידה מתמטית: התרחבות גבולות הגזרה של שריפה (Bounding Box).
    מוודא שכאשר מגיעות תצפיות חדשות בקצוות שונים, הקופסה הווירטואלית גדלה
    והמרכז (Center) מחושב מחדש בצורה הנדסית ומדויקת.
    """
    monitor = MonitorAgent()

    # 1. נייצר אירוע בסיסי (נקודה אחת במרכז אידיאלי)
    base_read = MockFireIncident(id=1, lat=32.0, lon=35.0, brightness=300, frp=20)
    event = monitor._create_new_event(base_read)

    # נוודא שהקופסה ההתחלתית היא נקודתית בלבד
    assert event.min_lat == 32.0 and event.max_lat == 32.0
    assert event.min_lon == 35.0 and event.max_lon == 35.0

    # 2. כעת "נפציץ" את השריפה מ-4 כיוונים שונים כדי להרחיב את הגזרה

    # תצפית צפונית
    north_read = MockFireIncident(id=2, lat=32.1, lon=35.0, brightness=300, frp=20)
    monitor._update_existing_event(event, north_read)

    # תצפית דרומית
    south_read = MockFireIncident(id=3, lat=31.9, lon=35.0, brightness=300, frp=20)
    monitor._update_existing_event(event, south_read)

    # תצפית מזרחית
    east_read = MockFireIncident(id=4, lat=32.0, lon=35.1, brightness=300, frp=20)
    monitor._update_existing_event(event, east_read)

    # תצפית מערבית
    west_read = MockFireIncident(id=5, lat=32.0, lon=34.9, brightness=300, frp=20)
    monitor._update_existing_event(event, west_read)

    # === מבחני התוצאה (Assertions) ===

    # 3. בדיקת גבולות הקופסה (Bounding Box)
    assert event.max_lat == 32.1, "הגבול הצפוני לא התרחב!"
    assert event.min_lat == 31.9, "הגבול הדרומי לא התרחב!"
    assert event.max_lon == 35.1, "הגבול המזרחי לא התרחב!"
    assert event.min_lon == 34.9, "הגבול המערבי לא התרחב!"

    # 4. בדיקת המרכז (Center)
    # מאחר והרחבנו את השריפה באופן סימטרי בדיוק לכל הכיוונים,
    # הממוצע (המרכז) חייב לחזור לאותה נקודת ההתחלה!
    assert event.latitude == 32.0, "שגיאה בחישוב קו הרוחב המרכזי!"
    assert event.longitude == 35.0, "שגיאה בחישוב קו האורך המרכזי!"

    # 5. בדיקת מונים
    assert event.num_points == 5, "מונה הנקודות לא צבר את התצפיות נכון"