from app.agents.commander_agent import CommanderAgent
from app.models.fire_events import FireEvent
from app.models.resources import Resource


def test_steep_terrain_specialization(app):
    """Tests that the system correctly prioritizes off-road capable vehicles (ROTEM) over urban vehicles (SAAR) when responding to fires in steep forest terrain with slopes of 25 degrees, even when the off-road vehicle has a longer ETA, ensuring terrain traversability is properly evaluated."""
    commander = CommanderAgent()

    # Create a forest fire event with steep slope requiring off-road capable vehicles
    steep_forest_fire = FireEvent(id=1, latitude=32.5, longitude=35.0,
                                  fuel_type="FOREST", topo_slope=25.0,
                                  demand_perimeter_m=100.0)

    # Urban vehicle nearby but cannot traverse steep terrain effectively
    saar_close = Resource(id=10, resource_type='SAAR', status='AVAILABLE')
    # Off-road vehicle farther away but has good traversability on difficult terrain
    rotem_far = Resource(id=11, resource_type='ROTEM', status='AVAILABLE')

    # ETA matrix: SAAR is 5 minutes away, ROTEM is 20 minutes away
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

    # Verify ROTEM was dispatched since SAAR has zero effectiveness on steep slopes
    assert rotem_far.status == 'EN_ROUTE', "System failed: dispatched non-traversable vehicle instead of distant off-road vehicle"
    assert saar_close.status == 'AVAILABLE'


def test_high_risk_priority(app):
    """Tests that the dispatch system correctly prioritizes fires based on risk level when resources are limited, verifying that a single available vehicle is assigned to an extreme risk fire rather than a low risk fire, even when both fires have similar ETAs."""
    commander = CommanderAgent()

    # Create two fire events with different risk levels
    fire_high_risk = FireEvent(id=2, demand_perimeter_m=100.0)
    fire_low_risk = FireEvent(id=3, demand_perimeter_m=100.0)

    # Assign risk levels used by Commander's objective function for prioritization
    fire_high_risk.pred_risk_level = "EXTREME"
    fire_low_risk.pred_risk_level = "LOW"

    # Single available resource must choose between the two fires
    single_rotem = Resource(id=20, resource_type='ROTEM', status='AVAILABLE')

    # Both fires have similar ETAs, so risk level should determine assignment
    eta_matrix = {20: {2: 10.0 / 60.0, 3: 12.0 / 60.0}}

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

    # Verify the resource was assigned to the extreme risk fire, not the low risk fire
    assert single_rotem.assigned_event_id == 2, "System failed to prioritize high-risk fire!"
