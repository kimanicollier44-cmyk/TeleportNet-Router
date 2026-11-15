"""Tests for TeleportNet-Router (pure stdlib, deterministic)."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main as m


# ---- physics layer (cross-checked vs EntangleNet-Q) ----

def test_werner_roundtrip():
    assert abs(m.werner_w_from_fidelity(m.werner_fidelity_from_w(0.6)) - 0.6) < 1e-12


def test_link_fidelity_zero_distance():
    assert m.link_fidelity(0.0) == 1.0


def test_link_fidelity_decreases():
    assert m.link_fidelity(100.0) > m.link_fidelity(400.0) > m.link_fidelity(1200.0)


def test_purify_threshold_behavior():
    assert m.purify_fidelity(0.8) > 0.8
    assert abs(m.purify_fidelity(0.5) - 0.5) < 1e-12
    assert m.purify_fidelity(0.4) < 0.4


def test_purify_rounds_entanglenet_value():
    assert abs(m.purify_rounds(0.75, 6) - 0.9446) < 1e-3


def test_chain_fidelity_entanglenet_value():
    path = m.fidelity_path("Los Angeles", "Dallas")
    assert abs(m.path_fidelity(path) - 0.5022) < 1e-3


def test_teleport_raw_entanglenet_value():
    path = m.fidelity_path("Los Angeles", "Dallas")
    assert abs(m.teleport_fidelity_from_pair(m.path_fidelity(path)) - 0.6681) < 1e-3


def test_teleport_purified_entanglenet_value():
    path = m.fidelity_path("Los Angeles", "Dallas")
    pur = m.chain_fidelity([m.purify_rounds(f, 2)
                            for f in m.path_link_fidelities(path)])
    assert abs(m.teleport_fidelity_from_pair(pur) - 0.7335) < 1e-3


def test_teleport_endpoints():
    assert m.teleport_fidelity_from_pair(1.0) == 1.0
    assert abs(m.teleport_fidelity_from_pair(0.25) - 0.5) < 1e-12


# ---- strategies ----

def test_strategies_differ():
    comp = m.compare_strategies()["strategies"]
    assert comp["latency"]["path"] != comp["fidelity"]["path"]


def test_latency_faster_but_worse():
    comp = m.compare_strategies()["strategies"]
    assert comp["latency"]["schedule_s"] < comp["fidelity"]["schedule_s"]
    assert comp["latency"]["pair_fidelity"] < comp["fidelity"]["pair_fidelity"]
    # latency path's teleport fidelity falls below the classical limit
    assert comp["latency"]["teleport_fidelity"] < 2.0 / 3.0


def test_fidelity_path_phoenix_via_vegas():
    assert m.fidelity_path("Los Angeles", "Phoenix") == [
        "Los Angeles", "Las Vegas", "Phoenix"]


def test_balanced_path_valid():
    path = m.balanced_path("Los Angeles", "Dallas")
    assert path[0] == "Los Angeles" and path[-1] == "Dallas"


# ---- purification planning ----

def test_plan_reaches_target_decay_aware():
    plan = m.plan_purification(m.fidelity_path("Los Angeles", "Dallas"), 0.55)
    assert plan["reachable"]
    assert plan["end_fidelity_after_memory"] >= 0.55
    assert plan["end_fidelity_after_memory"] < plan["end_fidelity_fresh"]


def test_plan_unneeded_is_free():
    plan = m.plan_purification(m.fidelity_path("Los Angeles", "Phoenix"), 0.45)
    assert plan["rounds_per_link"] == [0, 0]
    assert plan["pairs_expected"] == 2.0
    assert plan["purify_time_s"] == 0.0


def test_plan_unreachable_target():
    plan = m.plan_purification(m.fidelity_path("Los Angeles", "Dallas"), 0.99)
    assert not plan["reachable"]
    assert max(plan["rounds_per_link"]) == m.MAX_PURIFY_ROUNDS


def test_pairs_grow_with_rounds():
    assert m.link_pairs_expected(0.8, 2) > m.link_pairs_expected(0.8, 1) > 1.0


# ---- sessions ----

def _sess(req_id):
    return {s["id"]: m.plan_session(s) for s in m.demo_sessions()}[req_id]


def test_session_routed_raw():
    assert _sess("phoenix-express")["status"] == "ROUTED"


def test_session_routed_with_purification():
    p = _sess("dallas-purified")
    assert p["status"] == "ROUTED_WITH_PURIFICATION"
    assert p["end_fidelity_after_memory"] >= 0.55
    assert p["total_time_s"] <= 5.0


def test_session_no_route_deadline():
    p = _sess("dallas-impossible-deadline")
    assert p["status"] == "NO_ROUTE" and "deadline" in p["reason"]


def test_session_no_route_fidelity():
    p = _sess("dallas-impossible-fidelity")
    assert p["status"] == "NO_ROUTE" and "unreachable" in p["reason"]


def test_session_hold_living_being():
    p = _sess("cat-to-dallas")
    assert p["status"] == "HOLD" and p["gate"] == "teleport_living_being_claim"


def test_session_hold_matter():
    p = m.plan_session(m.make_request("rock", "Los Angeles", "Dallas", 0.5, 10.0,
                                      payload_kind="matter", payload_label="a rock"))
    assert p["status"] == "HOLD" and p["gate"] == "teleport_matter_claim"


def test_classical_accounting():
    p = _sess("dallas-purified")
    assert p["classical_bits"] == 2
    assert p["total_time_s"] > p["classical_transit_s"]
    assert abs(p["classical_transit_s"]
               - p["distance_km"] / m.C_FIBER_KM_S) < 1e-6


# ---- contention ----

def test_contention_outcomes():
    alloc = {r["id"]: r for r in m.allocate_sessions(m.contention_sessions())}
    assert alloc["c3-phoenix"]["status"] == "ROUTED"
    assert alloc["c3-phoenix"]["start_s"] == 0.0
    assert alloc["c2-dallas"]["status"] == "ROUTED_WITH_PURIFICATION"
    assert alloc["c2-dallas"]["start_s"] > 0.0
    assert alloc["c2-dallas"]["finish_s"] <= 1.2
    assert alloc["c1-vegas-dallas"]["status"] == "QUEUED_HELD"


def test_contention_victim_feasible_alone():
    solo = m.plan_session(m.contention_sessions()[2])
    assert solo["status"] in ("ROUTED", "ROUTED_WITH_PURIFICATION")
    assert solo["total_time_s"] <= 1.4


def test_contention_deterministic():
    a = m.allocate_sessions(m.contention_sessions())
    b = m.allocate_sessions(m.contention_sessions())
    assert a == b


# ---- failure handling ----

def test_reroute_survives_longer():
    req = m.make_request("fragile", "Los Angeles", "Dallas", 0.55, 5.0)
    rr = m.reroute_session(req, ("Phoenix", "Dallas"))
    assert rr["survives"]
    assert rr["after"]["status"] == "ROUTED_WITH_PURIFICATION"
    assert ("Phoenix", "Dallas") not in m.path_edges(rr["after"]["path"])
    assert rr["after"]["distance_km"] > rr["before"]["distance_km"]
    assert rr["after"]["end_fidelity_after_memory"] >= 0.55


# ---- classifier ----

def test_classifier_labels():
    reg = m.session_regime_report()
    assert reg["short_easy_session"] == "feasible"
    assert reg["long_hard_session"] == "needs-purification"
    assert reg["impossible_session"] == "infeasible"


# ---- gates and seats ----

def test_hold_gates():
    assert len(m.HOLD_GATES) == 14
    assert m.gate("teleport_matter_claim") == "HOLD"
    assert m.gate("claim_ftl_communication") == "HOLD"
    assert m.gate("run_simulation") == "PROCEED"


def test_seats_never_override():
    b = m.brains_report()
    assert b["decider"]["can_override_hold"] is False
    assert b["advisor"]["can_override_hold"] is False
    assert b["flow"]["rendered"] is False and b["flow"]["live"] == 0


def test_demo_runs(capsys):
    assert m.demo() == 0
    out = capsys.readouterr().out
    assert "CHECKS 47/47" in out and "VERDICT PROCEED" in out


def test_hold_demo_exit_codes():
    assert m.main(["hold-demo", "teleport_living_being_claim"]) == 2
    assert m.main(["hold-demo", "run_simulation"]) == 0
