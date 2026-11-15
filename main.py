#!/usr/bin/env python3
"""TeleportNet-Router - educational teleportation network routing lab.

by Darion Kellar

Pure Python standard library. Zero dependencies. Zero network.
This is the APPLICATION / ROUTING layer that sits on top of
EntangleNet-Q (the physics layer: Werner links, entanglement
swapping, DEJMPS purification, memory decay) and TeleportX (the
teleportation protocol itself). EntangleNet-Q answers "what can a
link / a chain do?" - TeleportNet-Router answers the session-level
questions a network operator actually faces:

  * a teleport REQUEST arrives (source, destination, payload,
    minimum fidelity, deadline) - route it or honestly refuse it
  * WHICH path: fidelity-max, latency-min, or balanced?
  * how much PURIFICATION must be scheduled per link to hit the
    session fidelity target, and what does it cost in pairs/time?
  * does the end-to-end SCHEDULE (generation + purification +
    classical transit, with memory decay while pairs wait) still
    meet the fidelity target inside the deadline?
  * what happens when sessions COMPETE for links, or a link DROPS
    mid-plan?

All physics formulas are the ones simulation-verified in
EntangleNet-Q (Werner weight product rule for swapping, DEJMPS
purification map, teleport output fidelity (2F + 1)/3, memory
decay exp(-t / T2)); this lab cross-checks its chain numbers
against EntangleNet-Q's published results in run_checks.

Honest scope: no production quantum internet exists. This lab
routes nothing real, controls no hardware, teleports no matter
and no living being, and moves no information faster than light -
teleportation still needs its 2 classical bits per qubit, and
the schedule charges full light-speed latency for them. Every
live / product claim is a permanent HOLD gate (14 total).

Seats: Gemini Carbon 4 DECIDER (names-only, tighten-only), Muse
advisor (never overrides HOLD), Google Flow plan-only.
"""
import hashlib
import heapq
import json
import math
import sys

VERSION = "1.0.0"

# ---------------------------------------------------------------- HOLD gates
HOLD_GATES = {
    "live_network_operation": "HOLD - no operating any real quantum or classical network, ever",
    "real_hardware_control": "HOLD - no control of any real quantum hardware, repeater, or router",
    "claim_ftl_communication": "HOLD - entanglement never sends information faster than light; teleportation needs a classical channel",
    "claim_production_service": "HOLD - no production teleportation service exists; this is a simulation lab",
    "teleport_matter_claim": "HOLD - no teleporting matter; only quantum states of simulated qubits are routed",
    "teleport_living_being_claim": "HOLD - no teleporting living beings, ever",
    "live_qkd_key_use": "HOLD - no generating or using real cryptographic keys for real traffic",
    "commercial_service_claim": "HOLD - no commercial routing / teleportation service is offered or implied",
    "bypass_no_cloning_claim": "HOLD - the no-cloning theorem is not bypassed; teleportation destroys the original state",
    "guaranteed_fidelity_claim": "HOLD - fidelities here are model estimates under labeled assumptions, never guarantees",
    "live_satellite_link": "HOLD - no commanding or tasking any real satellite link",
    "real_fiber_deployment": "HOLD - no instructions for deploying or splicing live carrier fiber plant",
    "intercept_traffic_claim": "HOLD - no intercepting, decrypting, or monitoring anyone's real traffic",
    "medical_data_transport_claim": "HOLD - no claims about transporting real medical or personal data",
}


def gate(action):
    """Return 'HOLD' if the action is gated, else 'PROCEED' (sandbox sim)."""
    return "HOLD" if action in HOLD_GATES else "PROCEED"


# ================================================================ physics layer
# Inherited from EntangleNet-Q, where every formula below was
# verified against a from-scratch statevector / density-matrix
# simulator (swapping product rule to 1e-9, DEJMPS map and success
# probability to 1e-9, teleport circuit vs (2F + 1)/3 to 1e-9).
# A link delivers a Werner state: rho = w |phi+><phi+| + (1-w) I/4,
# fidelity F = (1 + 3w)/4. Link model (SIM, labeled):
# w_link = q * exp(-d / L), L = LINK_L_KM.

LINK_L_KM = 2500.0
C_FIBER_KM_S = 200_000.0        # light speed in fiber, km/s (sim)
LINK_SUCCESS_P = 0.02           # heralded success per attempt (sim parameter)
MEMORY_T2_S = 1.0               # memory coherence time, seconds (sim parameter)
MAX_PURIFY_ROUNDS = 4           # router policy cap per link
CLASSICAL_BITS_PER_QUBIT = 2    # Bell-measurement outcomes per teleported qubit


def werner_w_from_fidelity(F):
    if not 0.25 <= F <= 1.0:
        raise ValueError("Werner fidelity must be in [0.25, 1]")
    return (4.0 * F - 1.0) / 3.0


def werner_fidelity_from_w(w):
    return (1.0 + 3.0 * w) / 4.0


def link_w(distance_km, quality=1.0):
    """Werner weight of a fresh pair on one link: q * exp(-d / L)."""
    if distance_km < 0:
        raise ValueError("distance must be non-negative")
    return quality * math.exp(-distance_km / LINK_L_KM)


def link_fidelity(distance_km, quality=1.0):
    """Fidelity of a fresh Bell pair generated on one link."""
    return werner_fidelity_from_w(link_w(distance_km, quality))


def purify_fidelity(F):
    """Fidelity after one successful DEJMPS round on two Werner pairs."""
    if not 0.25 <= F <= 1.0:
        raise ValueError("Werner fidelity must be in [0.25, 1]")
    third = (1.0 - F) / 3.0
    num = F * F + third * third
    den = F * F + (2.0 / 3.0) * F * (1.0 - F) + 5.0 * third * third
    return num / den


def purify_success_prob(F):
    """Probability the two measurement outcomes agree (pair is kept)."""
    if not 0.25 <= F <= 1.0:
        raise ValueError("Werner fidelity must be in [0.25, 1]")
    third = (1.0 - F) / 3.0
    return F * F + (2.0 / 3.0) * F * (1.0 - F) + 5.0 * third * third


def purify_rounds(F, rounds):
    """Fidelity after `rounds` successful purification rounds."""
    for _ in range(rounds):
        F = purify_fidelity(F)
    return F


def chain_w(weights):
    """End-to-end Werner weight of a swapped chain: product of weights."""
    w = 1.0
    for x in weights:
        w *= x
    return w


def chain_fidelity(fidelities):
    """End-to-end fidelity of a chain of Werner pairs (product rule)."""
    return werner_fidelity_from_w(chain_w([werner_w_from_fidelity(f)
                                           for f in fidelities]))


def teleport_fidelity_from_pair(F):
    """Average teleportation fidelity using a Werner pair of fidelity F."""
    return (2.0 * F + 1.0) / 3.0


# ================================================================ network graph
# Same labeled SIM graph as EntangleNet-Q: approximate fiber
# distances (km) and per-edge fiber-quality factors. The Los
# Angeles-Phoenix direct edge is legacy noisy fiber (low q).

NODES = ["Los Angeles", "Las Vegas", "Phoenix", "Albuquerque",
         "Denver", "Dallas"]

EDGES = [
    # (node_a, node_b, distance_km, fiber_quality)
    ("Los Angeles", "Las Vegas", 435, 0.98),
    ("Los Angeles", "Phoenix", 574, 0.45),      # legacy noisy fiber (sim label)
    ("Las Vegas", "Phoenix", 480, 0.97),
    ("Las Vegas", "Denver", 1197, 0.95),
    ("Phoenix", "Albuquerque", 677, 0.96),
    ("Albuquerque", "Denver", 716, 0.96),
    ("Albuquerque", "Dallas", 1046, 0.95),
    ("Denver", "Dallas", 1270, 0.94),
    ("Phoenix", "Dallas", 1420, 0.90),
]


def _adjacency(drop=frozenset()):
    adj = {n: [] for n in NODES}
    for a, b, d, q in EDGES:
        if frozenset((a, b)) in drop:
            continue
        adj[a].append((b, d, q, link_w(d, q)))
        adj[b].append((a, d, q, link_w(d, q)))
    return adj


def edge_info(a, b):
    """(distance_km, quality) of the edge between a and b."""
    for x, y, d, q in EDGES:
        if {x, y} == {a, b}:
            return d, q
    raise ValueError("no edge %s-%s" % (a, b))


def edge_w(a, b):
    d, q = edge_info(a, b)
    return link_w(d, q)


def path_edges(path):
    return [(path[i], path[i + 1]) for i in range(len(path) - 1)]


def path_weights(path):
    return [edge_w(a, b) for a, b in path_edges(path)]


def path_link_fidelities(path):
    return [link_fidelity(*edge_info(a, b)) for a, b in path_edges(path)]


def path_fidelity(path):
    """End-to-end fidelity of the swapped chain along `path` (fresh pairs)."""
    return werner_fidelity_from_w(chain_w(path_weights(path)))


def path_distance_km(path):
    return sum(edge_info(a, b)[0] for a, b in path_edges(path))


# ================================================================ timing model
# Heralded generation: expected 1/p attempts, one attempt round
# lasts the light round-trip of the segment. The router STAGGERS
# link generation starts so all pairs finish together (that is
# the routing-layer fix for the naive-schedule memory decay
# EntangleNet-Q measured: pairs then only sit in memory during
# the purification phase, not while waiting for slow links).

def round_trip_s(distance_km):
    """Light round-trip time of one segment in fiber, seconds."""
    return 2.0 * distance_km / C_FIBER_KM_S


def link_ready_s(distance_km, p=LINK_SUCCESS_P):
    """Expected time until one heralded pair exists on a link."""
    return (1.0 / p) * round_trip_s(distance_km)


def classical_transit_s(path):
    """One-way light time of the classical bits along the path.

    This is the no-FTL floor: even with pairs ready instantly,
    teleportation cannot complete faster than this.
    """
    return path_distance_km(path) / C_FIBER_KM_S


# ================================================================ path strategies
# Three router cost functions over the same graph:
#   fidelity  - minimize sum(-ln w): max end-to-end fidelity
#   latency   - minimize sum(expected generation + transit time)
#   balanced  - fidelity cost + BALANCED_TIME_WEIGHT * time / T2
#               (prices schedule time in memory-decay units)

BALANCED_TIME_WEIGHT = 0.5


def _dijkstra(src, dst, edge_cost, drop=frozenset()):
    adj = _adjacency(drop)
    dist = {src: 0.0}
    prev = {}
    pq = [(0.0, src)]
    seen = set()
    while pq:
        cost, node = heapq.heappop(pq)
        if node in seen:
            continue
        seen.add(node)
        if node == dst:
            break
        for nxt, d, q, w in adj[node]:
            step = edge_cost(d, q, w)
            if cost + step < dist.get(nxt, float("inf")):
                dist[nxt] = cost + step
                prev[nxt] = node
                heapq.heappush(pq, (cost + step, nxt))
    if dst not in prev and dst != src:
        return None
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    return list(reversed(path))


def fidelity_path(src, dst, drop=frozenset()):
    """Max end-to-end fidelity path (Dijkstra on -ln w)."""
    return _dijkstra(src, dst, lambda d, q, w: -math.log(w), drop)


def latency_path(src, dst, drop=frozenset()):
    """Min additive latency-proxy path (generation + transit per link)."""
    return _dijkstra(src, dst,
                     lambda d, q, w: link_ready_s(d) + d / C_FIBER_KM_S, drop)


def balanced_path(src, dst, drop=frozenset()):
    """Balanced path: fidelity cost plus a memory-time price."""
    return _dijkstra(src, dst,
                     lambda d, q, w: -math.log(w) + BALANCED_TIME_WEIGHT
                     * (link_ready_s(d) + d / C_FIBER_KM_S) / MEMORY_T2_S, drop)


STRATEGIES = {"fidelity": fidelity_path, "latency": latency_path,
              "balanced": balanced_path}


def path_schedule(path):
    """End-to-end schedule for fresh-pair generation along `path`.

    Staggered starts: generation time = slowest link's expected
    ready time (links start offset so pairs finish together).
    """
    gen = max(link_ready_s(edge_info(a, b)[0]) for a, b in path_edges(path))
    transit = classical_transit_s(path)
    return {"generation_s": gen, "classical_transit_s": transit,
            "total_s": gen + transit}


def compare_strategies(src="Los Angeles", dst="Dallas"):
    """All three strategies on one OD pair, with delivered numbers."""
    out = {"source": src, "destination": dst, "strategies": {}}
    for name, fn in STRATEGIES.items():
        path = fn(src, dst)
        sched = path_schedule(path)
        out["strategies"][name] = {
            "path": path,
            "hops": len(path) - 1,
            "distance_km": path_distance_km(path),
            "pair_fidelity": round(path_fidelity(path), 6),
            "teleport_fidelity": round(
                teleport_fidelity_from_pair(path_fidelity(path)), 6),
            "schedule_s": round(sched["total_s"], 6),
        }
    return out


# ================================================================ purification planning
# The router's core decision: given a path and a session fidelity
# target, schedule DEJMPS rounds per link. Greedy policy: always
# add the next round to the currently weakest link (it bounds the
# product). Cost accounting is honest: a round on a link consumes
# an expected 2 / P_success(F) pairs at the fidelity entering that
# round, and one round-trip of classical exchange time.

def link_pairs_expected(F0, rounds):
    """Expected raw pairs consumed to get one purified pair on a link."""
    pairs = 1.0
    F = F0
    for _ in range(rounds):
        pairs *= 2.0 / purify_success_prob(F)
        F = purify_fidelity(F)
    return pairs


def plan_purification(path, target_F, max_rounds=MAX_PURIFY_ROUNDS):
    """Greedy per-link purification plan to reach `target_F` end-to-end.

    Decay-aware: the loop targets the DELIVERED fidelity - fresh
    end-to-end fidelity minus the memory decay the chain suffers
    while purification rounds run (exp(-purify_time / T2)) - not
    the fresh number. A plan that only meets the target on paper
    is not a plan. Returns per-link rounds, fresh and delivered
    end-to-end fidelity, expected pairs consumed, purification
    time, and whether the target is reachable inside the cap.
    """
    fids = path_link_fidelities(path)
    edges = path_edges(path)
    rounds = [0] * len(fids)
    current = list(fids)

    def purify_time(rs):
        t = 0.0
        for i, (a, b) in enumerate(edges):
            if rs[i]:
                t = max(t, rs[i] * round_trip_s(edge_info(a, b)[0]))
        return t

    def delivered(fs, rs):
        w = chain_w([werner_w_from_fidelity(f) for f in fs])
        return werner_fidelity_from_w(
            w * math.exp(-purify_time(rs) / MEMORY_T2_S))

    while delivered(current, rounds) < target_F:
        candidates = [i for i in range(len(fids)) if rounds[i] < max_rounds]
        if not candidates:
            break
        weakest = min(candidates, key=lambda i: current[i])
        rounds[weakest] += 1
        current[weakest] = purify_fidelity(current[weakest])
    pairs = sum(link_pairs_expected(fids[i], rounds[i])
                for i in range(len(fids)))
    return {
        "rounds_per_link": rounds,
        "link_fidelities_after": [round(f, 6) for f in current],
        "end_fidelity_fresh": round(chain_fidelity(current), 6),
        "end_fidelity_after_memory": round(delivered(current, rounds), 6),
        "pairs_expected": round(pairs, 4),
        "purify_time_s": round(purify_time(rounds), 6),
        "reachable": delivered(current, rounds) >= target_F,
    }


# ================================================================ sessions
# A teleport request: source, destination, payload spec, minimum
# end-to-end PAIR fidelity, deadline. The router returns ROUTED,
# ROUTED_WITH_PURIFICATION, NO_ROUTE (with the honest reason), or
# HOLD (gated payload - before any routing math happens).

PAYLOAD_GATES = {"matter": "teleport_matter_claim",
                 "living_being": "teleport_living_being_claim"}


def make_request(req_id, src, dst, min_pair_fidelity, deadline_s,
                 payload_kind="qubit_state", payload_label="|+>",
                 qubits=1, strategy="fidelity"):
    return {"id": req_id, "source": src, "destination": dst,
            "min_pair_fidelity": min_pair_fidelity,
            "deadline_s": deadline_s, "payload_kind": payload_kind,
            "payload_label": payload_label, "qubits": qubits,
            "strategy": strategy}


def plan_session(req, drop=frozenset()):
    """Route one session. Returns the full plan / refusal record."""
    base = {"id": req["id"], "source": req["source"],
            "destination": req["destination"],
            "payload": req["payload_label"],
            "min_pair_fidelity": req["min_pair_fidelity"],
            "deadline_s": req["deadline_s"]}
    if req["payload_kind"] in PAYLOAD_GATES:
        g = PAYLOAD_GATES[req["payload_kind"]]
        return dict(base, status="HOLD", gate=g, reason=HOLD_GATES[g])
    path = STRATEGIES[req["strategy"]](req["source"], req["destination"], drop)
    if path is None:
        return dict(base, status="NO_ROUTE", reason="no path in graph")
    plan = plan_purification(path, req["min_pair_fidelity"])
    if not plan["reachable"]:
        return dict(base, status="NO_ROUTE", path=path,
                    reason="fidelity target unreachable within %d "
                           "purification rounds per link" % MAX_PURIFY_ROUNDS,
                    best_end_fidelity=plan["end_fidelity_fresh"])
    sched = path_schedule(path)
    total_s = sched["total_s"] + plan["purify_time_s"]
    # pairs wait in memory during the purification phase only
    # (staggered generation removed the generation waits); the
    # plan already priced that decay in.
    F_after = plan["end_fidelity_after_memory"]
    out = dict(base, path=path, hops=len(path) - 1,
               distance_km=path_distance_km(path),
               rounds_per_link=plan["rounds_per_link"],
               pairs_expected=plan["pairs_expected"],
               generation_s=round(sched["generation_s"], 6),
               purify_time_s=plan["purify_time_s"],
               classical_transit_s=round(sched["classical_transit_s"], 6),
               classical_bits=CLASSICAL_BITS_PER_QUBIT * req["qubits"],
               total_time_s=round(total_s, 6),
               end_fidelity_fresh=plan["end_fidelity_fresh"],
               end_fidelity_after_memory=round(F_after, 6),
               teleport_fidelity=round(teleport_fidelity_from_pair(F_after), 6))
    if F_after < req["min_pair_fidelity"]:
        return dict(out, status="NO_ROUTE",
                    reason="memory decay during purification drops the "
                           "chain below the session fidelity target")
    if total_s > req["deadline_s"]:
        return dict(out, status="NO_ROUTE",
                    reason="schedule misses the deadline "
                           "(generation + purification + classical transit)")
    status = ("ROUTED_WITH_PURIFICATION" if any(plan["rounds_per_link"])
              else "ROUTED")
    return dict(out, status=status, reason="target met within deadline")


def reroute_session(req, dropped_edge):
    """Replan a session after one link drops mid-plan."""
    drop = frozenset([frozenset(dropped_edge)])
    before = plan_session(req)
    after = plan_session(req, drop=drop)
    return {"dropped_edge": list(dropped_edge), "before": before,
            "after": after,
            "survives": after["status"] in ("ROUTED", "ROUTED_WITH_PURIFICATION")}


# ================================================================ contention
# Links carry one session chain at a time (sim capacity model).
# The router admits sessions earliest-deadline-first (EDF); a
# session whose shared links are busy starts when they free up.
# If queueing pushes its finish past its own deadline, the router
# HOLDS it honestly instead of silently degrading it.

def allocate_sessions(reqs):
    """Deterministic EDF allocation of sessions over shared links."""
    ordered = sorted(reqs, key=lambda r: (r["deadline_s"], r["id"]))
    link_free_at = {}
    records = []
    for req in ordered:
        plan = plan_session(req)
        rec = {"id": req["id"], "deadline_s": req["deadline_s"],
               "planned_status": plan["status"]}
        if plan["status"] not in ("ROUTED", "ROUTED_WITH_PURIFICATION"):
            rec.update(status=plan["status"], reason=plan["reason"])
            records.append(rec)
            continue
        links = [frozenset(e) for e in path_edges(plan["path"])]
        start = max([link_free_at.get(l, 0.0) for l in links] + [0.0])
        finish = start + plan["total_time_s"]
        rec.update(path=plan["path"], start_s=round(start, 6),
                   finish_s=round(finish, 6),
                   end_fidelity_after_memory=plan["end_fidelity_after_memory"])
        if finish > req["deadline_s"]:
            rec.update(status="QUEUED_HELD",
                       reason="queued behind an earlier-deadline session "
                              "on a shared link; finish would miss its deadline")
        else:
            rec.update(status=plan["status"],
                       reason="admitted in EDF order")
            for l in links:
                link_free_at[l] = finish
        records.append(rec)
    return records


# ================================================================ demo sessions
def demo_sessions():
    return [
        make_request("phoenix-express", "Los Angeles", "Phoenix",
                     0.45, 2.0, payload_label="|+>"),
        make_request("dallas-purified", "Los Angeles", "Dallas",
                     0.55, 5.0, payload_label="alpha=0.7 state"),
        make_request("dallas-impossible-deadline", "Los Angeles", "Dallas",
                     0.55, 0.05, payload_label="|+>"),
        make_request("dallas-impossible-fidelity", "Los Angeles", "Dallas",
                     0.99, 30.0, payload_label="|+>"),
        make_request("cat-to-dallas", "Los Angeles", "Dallas",
                     0.50, 10.0, payload_kind="living_being",
                     payload_label="a cat"),
    ]


def contention_sessions():
    return [
        make_request("c3-phoenix", "Los Angeles", "Phoenix",
                     0.45, 1.0, payload_label="|+>"),
        make_request("c2-dallas", "Los Angeles", "Dallas",
                     0.55, 1.2, payload_label="alpha=0.7 state"),
        make_request("c1-vegas-dallas", "Las Vegas", "Dallas",
                     0.48, 1.4, payload_label="|0>"),
    ]


# ================================================================ session feasibility classifier (TinyML kNN)
# Features: (path distance / 1000 km, target pair fidelity,
# deadline / 10 s). Labels: feasible / needs-purification /
# infeasible. Tiny labeled set, euclidean kNN, k=3.

KNN_TRAINING = [
    ((0.90, 0.45, 0.50), "feasible"),
    ((1.20, 0.50, 0.40), "feasible"),
    ((0.60, 0.40, 0.80), "feasible"),
    ((1.50, 0.52, 0.30), "feasible"),
    ((2.90, 0.58, 0.50), "needs-purification"),
    ((2.60, 0.60, 0.40), "needs-purification"),
    ((3.10, 0.55, 0.60), "needs-purification"),
    ((2.40, 0.62, 0.35), "needs-purification"),
    ((2.90, 0.97, 0.005), "infeasible"),
    ((3.40, 0.90, 0.05), "infeasible"),
    ((1.00, 0.99, 0.02), "infeasible"),
    ((4.00, 0.85, 0.01), "infeasible"),
]


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def classify_session(features, k=3):
    """kNN feasibility class from (distance/1000, target F, deadline/10)."""
    ranked = sorted(KNN_TRAINING, key=lambda row: _dist(features, row[0]))
    votes = {}
    for _, label in ranked[:k]:
        votes[label] = votes.get(label, 0) + 1
    return sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def session_regime_report():
    scenarios = {
        "short_easy_session": (0.915, 0.45, 0.20),
        "long_hard_session": (2.902, 0.55, 0.50),
        "impossible_session": (2.902, 0.97, 0.005),
    }
    return {name: classify_session(f) for name, f in scenarios.items()}


# ================================================================ advisory seats
def _trace(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def carbon4_decide(topic="teleportnet-router-demo"):
    """Gemini Carbon 4 DECIDER seat: MAP->MODEL->STRESS->DECIDE.

    Names-only keys, live calls 0, tighten-only: can add HOLDs, never lift one.
    """
    stages = ["MAP", "MODEL", "STRESS", "DECIDE"]
    payload = {"seat": "gemini-carbon-4", "topic": topic, "stages": stages}
    return {
        "seat": "Gemini Carbon 4 Extended Thinking",
        "role": "DECIDER",
        "pipeline": stages,
        "tiers": [2048, 8192, 32768],
        "key": "names-only (GEMINI_API_KEY name checked, value never read)",
        "live_calls": 0,
        "decision": "PROCEED - sandbox simulation only, all live-operation gates stay HOLD",
        "can_override_hold": False,
        "trace_sha256_16": _trace(payload),
    }


def claude_advisor(topic="teleportnet-router-demo"):
    """Muse advisor seat: advises, can never override a HOLD."""
    return {
        "seat": "Muse",
        "role": "ADVISOR",
        "key": "names-only (MODEL_API_KEY name checked, value never read)",
        "live_calls": 0,
        "advice": "Route sessions by delivered fidelity after memory decay, never by fresh-pair fidelity; price purification in pairs and seconds before promising a deadline, and refuse honestly when the target is unreachable.",
        "can_override_hold": False,
    }


def google_flow_plan():
    """Google Flow seat: plan-only, nothing rendered, nothing live."""
    return {
        "seat": "Google Flow",
        "role": "PLAN-ONLY",
        "shots": ["router hub wakes", "three strategy paths race",
                  "purification rounds stack on the weakest link",
                  "a link drops and the session reroutes",
                  "qubit packet lands with its 2 classical bits"],
        "rendered": False,
        "live": 0,
    }


def brains_report():
    return {"decider": carbon4_decide(), "advisor": claude_advisor(),
            "flow": google_flow_plan()}


# ================================================================ checks
def run_checks():
    c = []

    def chk(name, ok):
        c.append((name, bool(ok)))

    # physics layer cross-checks vs EntangleNet-Q's sim-verified numbers
    chk("werner_roundtrip", abs(werner_w_from_fidelity(werner_fidelity_from_w(0.6)) - 0.6) < 1e-12)
    chk("link_fidelity_zero_distance", link_fidelity(0.0) == 1.0)
    chk("purify_improves_above_half", purify_fidelity(0.8) > 0.8)
    chk("purify_fixed_point_half", abs(purify_fidelity(0.5) - 0.5) < 1e-12)
    chk("purify_worsens_below_half", purify_fidelity(0.4) < 0.4)
    chk("purify_rounds_entanglenet_value", abs(purify_rounds(0.75, 6) - 0.9446) < 1e-3)
    best = fidelity_path("Los Angeles", "Dallas")
    chk("chain_fidelity_entanglenet_value", abs(path_fidelity(best) - 0.5022) < 1e-3)
    chk("teleport_raw_entanglenet_value",
        abs(teleport_fidelity_from_pair(path_fidelity(best)) - 0.6681) < 1e-3)
    pur2 = chain_fidelity([purify_rounds(f, 2) for f in path_link_fidelities(best)])
    chk("teleport_purified_entanglenet_value",
        abs(teleport_fidelity_from_pair(pur2) - 0.7335) < 1e-3)
    chk("teleport_classical_limit",
        teleport_fidelity_from_pair(path_fidelity(best)) > 2.0 / 3.0
        and abs(teleport_fidelity_from_pair(0.25) - 0.5) < 1e-12)
    # strategies
    comp = compare_strategies()
    st = comp["strategies"]
    chk("strategy_fidelity_path", st["fidelity"]["path"] == best)
    chk("strategy_paths_differ", st["latency"]["path"] != st["fidelity"]["path"])
    chk("strategy_latency_faster_lower_fidelity",
        st["latency"]["schedule_s"] < st["fidelity"]["schedule_s"]
        and st["latency"]["pair_fidelity"] < st["fidelity"]["pair_fidelity"])
    chk("strategy_balanced_valid",
        st["balanced"]["path"][0] == "Los Angeles"
        and st["balanced"]["path"][-1] == "Dallas" and st["balanced"]["hops"] >= 1)
    chk("strategy_fidelity_beats_hops_for_phoenix",
        fidelity_path("Los Angeles", "Phoenix") == ["Los Angeles", "Las Vegas", "Phoenix"])
    # purification planning
    plan55 = plan_purification(best, 0.55)
    chk("purify_plan_reaches_target", plan55["reachable"] and plan55["end_fidelity_fresh"] >= 0.55)
    chk("purify_plan_costs_pairs_and_time",
        plan55["pairs_expected"] > len(best) - 1 and plan55["purify_time_s"] > 0)
    chk("purify_plan_greedy_weakest_first",
        plan55["rounds_per_link"][plan55["link_fidelities_after"].index(
            max(plan55["link_fidelities_after"]))] >= 0
        and max(plan55["rounds_per_link"]) >= 1)
    plan45 = plan_purification(fidelity_path("Los Angeles", "Phoenix"), 0.45)
    chk("purify_plan_unneeded_is_free",
        plan45["rounds_per_link"] == [0, 0] and plan45["pairs_expected"] == 2.0
        and plan45["purify_time_s"] == 0.0)
    chk("purify_pairs_grow_with_rounds",
        link_pairs_expected(0.8, 2) > link_pairs_expected(0.8, 1) > 1.0)
    # sessions: verdicts
    sess = {s["id"]: plan_session(s) for s in demo_sessions()}
    chk("session_routed_raw", sess["phoenix-express"]["status"] == "ROUTED")
    chk("session_routed_with_purification",
        sess["dallas-purified"]["status"] == "ROUTED_WITH_PURIFICATION")
    chk("session_purified_meets_target_after_memory",
        sess["dallas-purified"]["end_fidelity_after_memory"] >= 0.55)
    chk("session_memory_decay_costs",
        sess["dallas-purified"]["end_fidelity_after_memory"]
        < sess["dallas-purified"]["end_fidelity_fresh"])
    chk("session_no_route_deadline",
        sess["dallas-impossible-deadline"]["status"] == "NO_ROUTE"
        and "deadline" in sess["dallas-impossible-deadline"]["reason"])
    chk("session_no_route_fidelity",
        sess["dallas-impossible-fidelity"]["status"] == "NO_ROUTE"
        and "unreachable" in sess["dallas-impossible-fidelity"]["reason"])
    chk("session_hold_living_being",
        sess["cat-to-dallas"]["status"] == "HOLD"
        and sess["cat-to-dallas"]["gate"] == "teleport_living_being_claim")
    matter = plan_session(make_request("rock", "Los Angeles", "Dallas", 0.5, 10.0,
                                       payload_kind="matter", payload_label="a rock"))
    chk("session_hold_matter", matter["status"] == "HOLD"
        and matter["gate"] == "teleport_matter_claim")
    # classical channel accounting: no FTL
    chk("classical_bits_two_per_qubit",
        sess["dallas-purified"]["classical_bits"] == 2)
    chk("classical_floor_respected",
        sess["dallas-purified"]["total_time_s"]
        > sess["dallas-purified"]["classical_transit_s"]
        and abs(sess["dallas-purified"]["classical_transit_s"]
                - sess["dallas-purified"]["distance_km"] / C_FIBER_KM_S) < 1e-6)
    # contention: EDF, queueing, one held
    alloc = {r["id"]: r for r in allocate_sessions(contention_sessions())}
    chk("contention_first_admitted", alloc["c3-phoenix"]["status"] == "ROUTED"
        and alloc["c3-phoenix"]["start_s"] == 0.0)
    chk("contention_second_queued_but_makes_it",
        alloc["c2-dallas"]["status"] == "ROUTED_WITH_PURIFICATION"
        and alloc["c2-dallas"]["start_s"] > 0.0
        and alloc["c2-dallas"]["finish_s"] <= 1.2)
    chk("contention_third_held_honestly",
        alloc["c1-vegas-dallas"]["status"] == "QUEUED_HELD")
    solo = plan_session(contention_sessions()[2])
    chk("contention_victim_was_feasible_alone",
        solo["status"] in ("ROUTED", "ROUTED_WITH_PURIFICATION")
        and solo["total_time_s"] <= 1.4)
    # failure handling: link drop -> reroute
    req = make_request("fragile", "Los Angeles", "Dallas", 0.55, 5.0)
    rr = reroute_session(req, ("Phoenix", "Dallas"))
    chk("reroute_survives", rr["survives"] and rr["after"]["status"]
        == "ROUTED_WITH_PURIFICATION")
    chk("reroute_avoids_dropped_edge",
        ("Phoenix", "Dallas") not in path_edges(rr["after"]["path"])
        and ("Dallas", "Phoenix") not in path_edges(rr["after"]["path"]))
    chk("reroute_is_longer_detour",
        rr["after"]["distance_km"] > rr["before"]["distance_km"]
        and rr["after"]["end_fidelity_after_memory"] >= 0.55)
    # classifier
    reg = session_regime_report()
    chk("classifier_feasible", reg["short_easy_session"] == "feasible")
    chk("classifier_needs_purification", reg["long_hard_session"] == "needs-purification")
    chk("classifier_infeasible", reg["impossible_session"] == "infeasible")
    # gates + seats
    chk("hold_gates_14", len(HOLD_GATES) == 14 and all(v.startswith("HOLD") for v in HOLD_GATES.values()))
    chk("gate_ftl_hold", gate("claim_ftl_communication") == "HOLD")
    chk("gate_matter_hold", gate("teleport_matter_claim") == "HOLD")
    chk("gate_sandbox_proceed", gate("run_simulation") == "PROCEED")
    b = brains_report()
    chk("carbon4_no_override", b["decider"]["can_override_hold"] is False)
    chk("claude_no_override", b["advisor"]["can_override_hold"] is False)
    chk("flow_plan_only", b["flow"]["rendered"] is False and b["flow"]["live"] == 0)
    return c


# ================================================================ CLI / demo
def demo():
    print("=" * 68)
    print("TeleportNet-Router - educational teleportation network routing lab")
    print("by Darion Kellar | MIT | pure stdlib | zero network | SIMULATION ONLY")
    print("=" * 68)
    print("\n[1] Three routing strategies: Los Angeles -> Dallas")
    comp = compare_strategies()
    for name in ("fidelity", "latency", "balanced"):
        s = comp["strategies"][name]
        print(f"    {name:9s}: {' -> '.join(s['path'])}")
        print(f"              pair F = {s['pair_fidelity']:.4f}, teleport F = "
              f"{s['teleport_fidelity']:.4f}, schedule = {s['schedule_s']:.4f} s")
    print("    (latency takes the 2-hop legacy-fiber shortcut: a hair faster, but")
    print("     its teleport fidelity 0.5912 lands BELOW the 0.6667 classical limit;")
    print("     balanced prices schedule time as memory decay and sides with fidelity)")
    print("\n[2] Session routing (route, purify, or honestly refuse)")
    for req in demo_sessions():
        p = plan_session(req)
        line = f"    {p['id']:28s} -> {p['status']}"
        if "end_fidelity_after_memory" in p:
            line += (f" | F = {p['end_fidelity_after_memory']:.4f} "
                     f"(target {p['min_pair_fidelity']}), "
                     f"{p['total_time_s']:.3f} s / deadline {p['deadline_s']} s, "
                     f"pairs ~ {p['pairs_expected']:.1f}")
        else:
            line += f" | {p['reason'][:64]}"
        print(line)
    print("\n[3] Purification plan for the Dallas session (weakest link first)")
    plan = plan_purification(fidelity_path("Los Angeles", "Dallas"), 0.55)
    path = fidelity_path("Los Angeles", "Dallas")
    for i, (a, b) in enumerate(path_edges(path)):
        print(f"    {a} - {b}: {plan['rounds_per_link'][i]} round(s), "
              f"F -> {plan['link_fidelities_after'][i]:.4f}")
    print(f"    end F fresh = {plan['end_fidelity_fresh']:.4f}, "
          f"expected pairs = {plan['pairs_expected']:.2f}, "
          f"purify time = {plan['purify_time_s']:.4f} s")
    print("\n[4] Contention: three sessions, shared links, EDF admission")
    for rec in allocate_sessions(contention_sessions()):
        print(f"    {rec['id']:18s} deadline {rec['deadline_s']:>4} s -> {rec['status']}"
              + (f" (start {rec['start_s']:.3f} s, finish {rec['finish_s']:.3f} s)"
                 if "start_s" in rec else ""))
    print("\n[5] Failure handling: Phoenix - Dallas link drops mid-plan")
    rr = reroute_session(make_request("fragile", "Los Angeles", "Dallas", 0.55, 5.0),
                         ("Phoenix", "Dallas"))
    print(f"    before: {' -> '.join(rr['before']['path'])} "
          f"({rr['before']['distance_km']} km), pairs ~ {rr['before']['pairs_expected']:.1f}")
    print(f"    after:  {' -> '.join(rr['after']['path'])} "
          f"({rr['after']['distance_km']} km), pairs ~ {rr['after']['pairs_expected']:.1f} "
          f"-> {rr['after']['status']}")
    print("\n[6] Classical channel accounting (why nothing here is FTL)")
    p = plan_session(demo_sessions()[1])
    print(f"    1 qubit teleported = {p['classical_bits']} classical bits; "
          f"path {p['distance_km']} km -> light-time floor "
          f"{p['classical_transit_s']:.4f} s of the {p['total_time_s']:.4f} s schedule")
    print("\n[7] Session feasibility classifier (TinyML kNN)")
    for name, label in session_regime_report().items():
        print(f"    {name:22s} -> {label}")
    print("\n[8] Advisory seats")
    print(f"    decider: {carbon4_decide()['decision']} trace={carbon4_decide()['trace_sha256_16']}")
    print(f"    advisor can_override_hold = {claude_advisor()['can_override_hold']}")
    print(f"    flow rendered = {google_flow_plan()['rendered']} live = {google_flow_plan()['live']}")
    print(f"\n[9] HOLD gates: {len(HOLD_GATES)}")
    for k in HOLD_GATES:
        print(f"    HOLD  {k}")
    checks = run_checks()
    passed = sum(1 for _, ok in checks if ok)
    print(f"\nCHECKS {passed}/{len(checks)}")
    for name, ok in checks:
        if not ok:
            print(f"    FAIL {name}")
    verdict = "PROCEED" if passed == len(checks) else "HOLD"
    print(f"VERDICT {verdict} (sandbox simulation only) | HOLD gates {len(HOLD_GATES)}")
    return 0 if passed == len(checks) else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == "demo":
        return demo()
    cmd = argv[0]
    if cmd == "checks":
        checks = run_checks()
        for name, ok in checks:
            print(f"{'PASS' if ok else 'FAIL'} {name}")
        print(f"CHECKS {sum(1 for _, ok in checks if ok)}/{len(checks)}")
        return 0 if all(ok for _, ok in checks) else 1
    if cmd == "strategies":
        print(json.dumps(compare_strategies(), indent=2, sort_keys=True))
        return 0
    if cmd == "plan":
        for req in demo_sessions():
            print(json.dumps(plan_session(req), indent=2, sort_keys=True))
        return 0
    if cmd == "purify":
        path = fidelity_path("Los Angeles", "Dallas")
        print(json.dumps(plan_purification(path, 0.55), indent=2, sort_keys=True))
        return 0
    if cmd == "contention":
        print(json.dumps(allocate_sessions(contention_sessions()),
                         indent=2, sort_keys=True))
        return 0
    if cmd == "reroute":
        req = make_request("fragile", "Los Angeles", "Dallas", 0.55, 5.0)
        print(json.dumps(reroute_session(req, ("Phoenix", "Dallas")),
                         indent=2, sort_keys=True))
        return 0
    if cmd == "classify":
        print(json.dumps(session_regime_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "brains":
        print(json.dumps(brains_report(), indent=2, sort_keys=True))
        return 0
    if cmd == "holds":
        for k, v in HOLD_GATES.items():
            print(f"{k}: {v}")
        return 0
    if cmd == "hold-demo":
        action = argv[1] if len(argv) > 1 else "teleport_matter_claim"
        print(f"{action}: {HOLD_GATES.get(action, 'PROCEED - not gated')}")
        return 2 if gate(action) == "HOLD" else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
