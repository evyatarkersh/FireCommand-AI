import pytest
from app.models.fire_events import FireEvent
from app.models.resources import Resource
from app.agents.commander_agent import CommanderAgent


def test_overkill_prevention_triple_layer(app):
    """
    מבחן התותח והזבוב:
    מוודא שהאלגוריתם בוחר כלי חלש ורחוק יותר (SAAR - 10 דקות)
    על פני כלי חזק וקרוב יותר (ROTEM - 5 דקות) עבור שריפה קטנה,
    כדי למזער את קנס ה'רזרבות' של פונקציית המטרה.
    """
    # 1. הקמת זירה פיקטיבית
    commander = CommanderAgent()

    # נייצר אובייקטים "מזויפים" (Mocks) כדי לא לערב את הדאטה-בייס האמיתי
    small_fire = FireEvent(id=1, demand_perimeter_m=80.0)

    saar_truck = Resource(id=101, resource_type='SAAR', status='AVAILABLE')
    rotem_truck = Resource(id=102, resource_type='ROTEM', status='AVAILABLE')

    unsolved_fires = [small_fire]
    math_survivors = [saar_truck, rotem_truck]

    # 2. זיוף מטריצת ה-OSRM (כדי לא לעשות קריאות API אמיתיות בטסט)
    # הרותם במרחק 5 דקות (0.083 שעות), הסער במרחק 10 דקות (0.166 שעות)
    eta_matrix = {
        101: {1: 10.0 / 60.0},  # SAAR -> Fire 1
        102: {1: 5.0 / 60.0}  # ROTEM -> Fire 1
    }

    fire_demands = {1: 80.0}
    allocated = set()
    llm_summary = {}

    # 3. הפעלת מנוע ה-MILP בלבד (Step 4)
    success = commander.step4_optimize_and_dispatch(
        unsolved_fires=unsolved_fires,
        math_survivors=math_survivors,
        eta_matrix=eta_matrix,
        time_horizon_hours=1.0,
        fire_demands=fire_demands,
        allocated_in_this_cycle=allocated,
        available_supply={"SAAR": [saar_truck], "ROTEM": [rotem_truck]},
        llm_summary=llm_summary,
        district_name="Test_District"
    )

    # 4. מבחני התוצאה (Assertions) - פה בודקים אם האלגוריתם עבר את המבחן
    assert success is True, "האלגוריתם לא מצא פתרון למרות שיש היתכנות ודאית!"

    # האם הוא בחר נכון? הוא היה אמור לבחור *רק* את הסער!
    assert saar_truck.status == 'EN_ROUTE', "המערכת הייתה צריכה לשלוח את ה-SAAR החלש יותר!"
    assert saar_truck.assigned_event_id == small_fire.id

    # והכי חשוב: האם הוא שמר את הרותם כרזרבה?
    assert rotem_truck.status == 'AVAILABLE', "כישלון! המערכת שלחה את ה-ROTEM היקר לשריפה קטנה למרות שיש SAAR!"


def test_swarm_prevention(app):
    """
    מבחן ריקון התחנות:
    מוודא שהמערכת מעדיפה כלי אחד חזק (ROTEM) מרחוק,
    על פני פיצול הכוח ושליחת 3 כלים חלשים (SAAR) מקרוב,
    כדי לחסוך את קנס היציאה (10,000) על הפעלת כלים רבים.
    """
    commander = CommanderAgent()

    # שריפה דורשת 250 מטר (ביער: רותם מפיק 320, סער מפיק 120. נדרשים 3 סערים או רותם 1)
    medium_fire = FireEvent(id=2, demand_perimeter_m=250.0)

    rotem_far = Resource(id=201, resource_type='ROTEM', status='AVAILABLE')
    saar_close_1 = Resource(id=202, resource_type='SAAR', status='AVAILABLE')
    saar_close_2 = Resource(id=203, resource_type='SAAR', status='AVAILABLE')
    saar_close_3 = Resource(id=204, resource_type='SAAR', status='AVAILABLE')

    math_survivors = [rotem_far, saar_close_1, saar_close_2, saar_close_3]

    # הרותם במרחק 25 דק', הסערים במרחק 5 דק'
    eta_matrix = {
        201: {2: 25.0 / 60.0},
        202: {2: 5.0 / 60.0},
        203: {2: 5.0 / 60.0},
        204: {2: 5.0 / 60.0}
    }

    success = commander.step4_optimize_and_dispatch(
        unsolved_fires=[medium_fire],
        math_survivors=math_survivors,
        eta_matrix=eta_matrix,
        time_horizon_hours=1.0,
        fire_demands={2: 250.0},
        allocated_in_this_cycle=set(),
        available_supply={"SAAR": [saar_close_1, saar_close_2, saar_close_3], "ROTEM": [rotem_far]},
        llm_summary={},
        district_name="Test_District"
    )

    assert success is True
    # המערכת חייבת לשלוח את הרותם הבודד כדי למזער את קנס 30,000 הנקודות של הסערים
    assert rotem_far.status == 'EN_ROUTE', "המערכת רוקנה את התחנות במקום לשלוח כלי אחד חזק!"
    assert saar_close_1.status == 'AVAILABLE'


def test_starvation_prevention(app):
    """
    מבחן ההרעבה:
    שתי שריפות (אחת גדולה, אחת קטנה). יש רק ROTEM אחד ו-SAAR אחד.
    ה-ROTEM קרוב לשריפה הקטנה, אבל המערכת חייבת לשלוח אותו לגדולה
    כדי לא "להרעיב" אותה ממשאבים שיכולים לסגור אותה.
    """
    commander = CommanderAgent()

    # שריפה 3 ענקית, שריפה 4 קטנה
    huge_fire = FireEvent(id=3, demand_perimeter_m=200.0)
    small_fire = FireEvent(id=4, demand_perimeter_m=50.0)

    rotem_truck = Resource(id=301, resource_type='ROTEM', status='AVAILABLE')
    saar_truck = Resource(id=302, resource_type='SAAR', status='AVAILABLE')

    # ה-ROTEM קרוב לשתיהן. ה-SAAR קרוב רק לגדולה.
    # אלגוריתם "טיפש" ישלח את ה-ROTEM לקטנה כי הוא הכי מהיר לשם.
    eta_matrix = {
        301: {3: 15.0 / 60.0, 4: 5.0 / 60.0},  # רותם: 15 דק לגדולה, 5 לקטנה
        302: {3: 10.0 / 60.0, 4: 30.0 / 60.0}  # סער: 10 דק לגדולה, 30 לקטנה
    }

    success = commander.step4_optimize_and_dispatch(
        unsolved_fires=[huge_fire, small_fire],
        math_survivors=[rotem_truck, saar_truck],
        eta_matrix=eta_matrix,
        time_horizon_hours=1.0,
        fire_demands={3: 200.0, 4: 50.0},
        allocated_in_this_cycle=set(),
        available_supply={"SAAR": [saar_truck], "ROTEM": [rotem_truck]},
        llm_summary={},
        district_name="Test_District"
    )

    assert success is True
    # המערכת הבינה שרק הרותם יכול לסגור את השריפה הגדולה, ולכן שידכה אותו אליה
    assert rotem_truck.assigned_event_id == 3, "כישלון: המערכת הרעיבה את השריפה הגדולה!"
    assert saar_truck.assigned_event_id == 4, "כישלון: המערכת לא שלחה את הסער לשריפה הקטנה!"