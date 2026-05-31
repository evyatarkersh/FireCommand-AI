from app.agents.commander_agent import CommanderAgent
from app.models.fire_events import FireEvent
from app.models.resources import Resource


def test_overkill_prevention_triple_layer(app):
    """Tests that the optimization algorithm chooses a weaker but adequate resource (SAAR at 10 minutes) over a stronger closer resource (ROTEM at 5 minutes) for a small fire, thereby minimizing the reserves penalty in the objective function and preventing resource overkill."""
    # Setup fictional scenario with commander agent
    commander = CommanderAgent()

    # Create mock fire and resource objects to avoid involving the real database
    small_fire = FireEvent(id=1, demand_perimeter_m=80.0)

    saar_truck = Resource(id=101, resource_type='SAAR', status='AVAILABLE')
    rotem_truck = Resource(id=102, resource_type='ROTEM', status='AVAILABLE')

    unsolved_fires = [small_fire]
    math_survivors = [saar_truck, rotem_truck]

    # Mock OSRM travel time matrix to avoid making real API calls in the test
    # ROTEM is closer at 5 minutes, SAAR is farther at 10 minutes
    eta_matrix = {
        101: {1: 10.0 / 60.0},  # SAAR -> Fire 1
        102: {1: 5.0 / 60.0}  # ROTEM -> Fire 1
    }

    fire_demands = {1: 80.0}
    allocated = set()
    llm_summary = {}

    # Run MILP optimization engine only
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

    # Verify that the algorithm found a solution
    assert success is True, "Algorithm failed to find a solution despite guaranteed feasibility!"

    # Verify that the weaker SAAR was chosen correctly
    assert saar_truck.status == 'EN_ROUTE', "System should have dispatched the weaker SAAR!"
    assert saar_truck.assigned_event_id == small_fire.id

    # Verify that ROTEM was kept in reserve instead of being dispatched to a small fire
    assert rotem_truck.status == 'AVAILABLE', "Failure! System dispatched the expensive ROTEM to a small fire despite having SAAR available!"


def test_swarm_prevention(app):
    """Tests that the system prefers dispatching one strong resource (ROTEM) from afar over deploying three weak resources (SAAR) from nearby, minimizing the deployment penalty for activating multiple resources and preventing station depletion."""
    commander = CommanderAgent()

    # Fire requires 250 meters perimeter coverage (in forest: ROTEM produces 320m, SAAR produces 120m, so requires 3 SAARs or 1 ROTEM)
    medium_fire = FireEvent(id=2, demand_perimeter_m=250.0)

    rotem_far = Resource(id=201, resource_type='ROTEM', status='AVAILABLE')
    saar_close_1 = Resource(id=202, resource_type='SAAR', status='AVAILABLE')
    saar_close_2 = Resource(id=203, resource_type='SAAR', status='AVAILABLE')
    saar_close_3 = Resource(id=204, resource_type='SAAR', status='AVAILABLE')

    math_survivors = [rotem_far, saar_close_1, saar_close_2, saar_close_3]

    # ROTEM is farther at 25 minutes, SAARs are closer at 5 minutes each
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
    # System must send the single ROTEM to minimize the deployment penalty of dispatching multiple SAARs
    assert rotem_far.status == 'EN_ROUTE', "System depleted the stations instead of sending one strong resource!"
    assert saar_close_1.status == 'AVAILABLE'


def test_starvation_prevention(app):
    """Tests that with two fires (one large, one small) and limited resources (one ROTEM, one SAAR), the system correctly assigns the ROTEM to the large fire despite it being closer to the small fire, preventing starvation of fires that require stronger resources."""
    commander = CommanderAgent()

    # Two fires with different demands: one large and one small
    huge_fire = FireEvent(id=3, demand_perimeter_m=200.0)
    small_fire = FireEvent(id=4, demand_perimeter_m=50.0)

    rotem_truck = Resource(id=301, resource_type='ROTEM', status='AVAILABLE')
    saar_truck = Resource(id=302, resource_type='SAAR', status='AVAILABLE')

    # ROTEM is close to both fires, SAAR is close only to the large one
    # A naive algorithm would send ROTEM to the small fire because it's the fastest route
    eta_matrix = {
        301: {3: 15.0 / 60.0, 4: 5.0 / 60.0},  # ROTEM: 15 min to large fire, 5 min to small fire
        302: {3: 10.0 / 60.0, 4: 30.0 / 60.0}  # SAAR: 10 min to large fire, 30 min to small fire
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
    # Verify that only ROTEM can handle the large fire, so it must be assigned there
    assert rotem_truck.assigned_event_id == 3, "Failure: The system starved the large fire!"
    assert saar_truck.assigned_event_id == 4, "Failure: The system didn't send SAAR to the small fire!"
