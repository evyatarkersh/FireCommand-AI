import pytest
from app.agents.commander_agent import CommanderAgent
from app.models.fire_events import FireEvent
from app.models.resources import Resource


def test_steep_terrain_specialization(app):
    """
    בדיקת היגיון: שטח תלול וקשה.
    מוודא שהמערכת לא שולחת רכב עירוני (SAAR) לשטח שהוא לא יכול לעבור בו,
    ומעדיפה רכב שטח (ROTEM) למרות שהוא רחוק יותר.
    """
    commander = CommanderAgent()

    # שריפה ביער (FOREST) עם שיפוע חד (25 מעלות)
    steep_forest_fire = FireEvent(id=1, latitude=32.5, longitude=35.0,
                                  fuel_type="FOREST", topo_slope=25.0,
                                  demand_perimeter_m=100.0)

    # סער קרוב (5 דקות) אבל עם עבירות 0 בשטח כזה
    saar_close = Resource(id=10, resource_type='SAAR', status='AVAILABLE')
    # רותם רחוק (20 דקות) אבל עביר (SDI=0.7)
    rotem_far = Resource(id=11, resource_type='ROTEM', status='AVAILABLE')

    eta_matrix = {
        10: {1: 5.0 / 60.0},
        11: {1: 20.0 / 60.0}
    }

    commander.step4_optimize_and_dispatch(
        unsolved_fires=[steep_forest_fire],
        math_survivors=[saar_close, rotem_far],
        eta_matrix=eta_matrix,
        time_horizon_hours=1.0,
        fire_demands={1: 100.0},
        allocated_in_this_cycle=set(),
        available_supply={"SAAR": [saar_close], "ROTEM": [rotem_far]},
        llm_summary={},
        district_name="North"
    )

    # המערכת חייבת לבחור ברותם. הסער לא מייצר תפוקה בשיפוע כזה (0 * base_rate = 0)
    assert rotem_far.status == 'EN_ROUTE', "המערכת כשלה: שלחה רכב לא עביר במקום רכב שטח רחוק"
    assert saar_close.status == 'AVAILABLE'


def test_high_risk_priority(app):
    """
    בדיקת היגיון: תעדוף לפי רמת סיכון.
    שתי שריפות דורשות את אותו הכלי. המערכת חייבת לתת אותו לשריפה עם ה-Risk הגבוה יותר.
    """
    commander = CommanderAgent()

    fire_high_risk = FireEvent(id=2, demand_perimeter_m=100.0)
    fire_low_risk = FireEvent(id=3, demand_perimeter_m=100.0)

    # נגדיר רמות סיכון (ה-Commander משתמש בזה בפונקציית המטרה שלו)
    fire_high_risk.pred_risk_level = "EXTREME"
    fire_low_risk.pred_risk_level = "LOW"

    # יש רק רותם אחד זמין
    single_rotem = Resource(id=20, resource_type='ROTEM', status='AVAILABLE')

    # שניהם באותו מרחק
    eta_matrix = {20: {2: 10.0/60.0, 3: 12.0/60.0}}

    commander.step4_optimize_and_dispatch(
        unsolved_fires=[fire_high_risk, fire_low_risk],
        math_survivors=[single_rotem],
        eta_matrix=eta_matrix,
        time_horizon_hours=1.0,
        fire_demands={2: 100.0, 3: 100.0},
        allocated_in_this_cycle=set(),
        available_supply={"ROTEM": [single_rotem]},
        llm_summary={},
        district_name="Center"
    )

    # הרותם חייב להשתבץ לשריפה בסיכון קיצון
    assert single_rotem.assigned_event_id == 2, "המערכת לא תיעדפה שריפה בסיכון גבוה!"