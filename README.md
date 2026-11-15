![TeleportNet-Router cover](assets/cover.png)

# TeleportNet-Router 🛰️⚛️

**Teleportation Network Routing Lab** — by Darion Kellar

## ❓ What is this?

TeleportNet-Router is an **educational teleportation routing lab** in ONE pure-Python file. It is the **application / routing layer** of Darion's quantum network stack, and it is deliberately *not* a repeat of the layers below it:

- **TeleportX** = the teleportation **protocol** (one hop, one Bell pair). 🌀
- **EntangleNet-Q** = the **physics layer**: what a link, a swap, a purification round, and a memory wait can and cannot do. 🔗
- **TeleportNet-Router** = the **routing layer**: what a network *operator* decides, session by session. 🛰️

A **teleport request** arrives — source, destination, payload, minimum fidelity, deadline — and the router must **route it, schedule its purification, fit it inside its deadline, share links fairly with other sessions, survive a link failure — or honestly refuse it** (`NO_ROUTE` / `HOLD`, with the reason printed). Every physics formula it plans with is the one simulation-verified in EntangleNet-Q (Werner product rule, DEJMPS map, teleport output `(2F + 1)/3`, memory decay `exp(-t / T2)`), and this lab cross-checks its chain numbers against EntangleNet-Q's published results in its own CHECKS. 🔬

Honest scope, stated up front: no production quantum internet or teleportation service exists. This lab routes **nothing real**: no network, no hardware, no matter, no living beings — and nothing faster than light, because every teleported qubit still pays for its **2 classical bits** at light speed. Every live / product claim sits behind a permanent HOLD gate (14 total). 🔒

## 🧰 Tech Stack Badges & Full Architecture

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Stdlib Only](https://img.shields.io/badge/Dependencies-Zero-2ea44f)
![Network](https://img.shields.io/badge/Network-Zero-2ea44f)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)
![CI](https://img.shields.io/badge/CI-Pending%20Paste-lightgrey)
![Docker Publish](https://img.shields.io/badge/Docker%20Publish-Pending%20Paste-lightgrey)

> ℹ️ Workflow badges are static **'Pending Paste'** shields on purpose: the `ci.yml` and `docker-publish.yml` files are delivered in the local paste pack and are **not pasted yet**, so no live badge is claimed.

**📦 1. Language & Runtime**
- 🐍 Python 3.12, pure standard library (`math`, `heapq`, `hashlib`, `json`, `sys`)
- 🚫 Zero dependencies, zero network, deterministic (double-run byte-identical)

**⚛️ 2. Quantum Core**
- 🔗 Werner link model inherited from EntangleNet-Q: `w = q · exp(-d / L)`, `F = (1 + 3w)/4`
- 🔀 Swapping product rule, DEJMPS purification map + success probability, teleport output `(2F + 1)/3`, memory T2 decay — formulas sim-verified in EntangleNet-Q, cross-checked here against its published numbers

**🛰️ 3. Routing / AI / ML**
- 🗺️ Three Dijkstra strategies (fidelity / latency / balanced), greedy decay-aware purification planner, EDF session allocator, failure rerouting
- 🧠 TinyML kNN session-feasibility classifier (from scratch, stdlib): feasible / needs-purification / infeasible
- 🔮 Gemini Carbon 4 DECIDER seat (names-only, tighten-only) + Muse advisor (never overrides HOLD)

**🎬 4. Media / Planning**
- 🎥 Google Flow plan-only seat (rendered = False, live = 0)

**🐳 5. Infrastructure**
- 🐳 Docker (`python:3.12-slim`), GitHub Actions CI + Docker Publish (paste pack)
- 🎯 Target image: `credkellar/teleportnet-router:latest`

**🔒 6. Safety**
- ⛔ 14 HOLD gates — live network operation, real hardware, FTL claims, production-service claims, teleporting matter or living beings, and more are permanently held

## 🔬 What this does

1. 📥 **Session model** — a request is `(source, destination, payload spec, minimum pair fidelity, deadline, qubits)`. Payloads of kind `matter` or `living_being` never reach the routing math: they return **HOLD** immediately, by gate.
2. 🗺️ **Three path strategies** — on the same labeled sim graph as EntangleNet-Q (Los Angeles / Las Vegas / Phoenix / Albuquerque / Denver / Dallas): **fidelity** (Dijkstra on −ln w), **latency** (expected generation + transit time), and **balanced** (fidelity cost + schedule time priced in memory-decay units). Los Angeles → Dallas: fidelity picks Las Vegas → Phoenix → Dallas (pair F = 0.5022, schedule 0.7217 s); latency takes the 2-hop legacy-fiber shortcut (0.7200 s) but delivers pair F = 0.3868 — a teleport fidelity of 0.5912, **below the 0.6667 classical limit**; balanced sides with fidelity.
3. ✨ **Purification scheduling** — a greedy planner adds DEJMPS rounds to the currently weakest link until the session target is met — planned against the **delivered** fidelity (fresh minus memory decay during the rounds), not the paper number. For the Dallas session (target 0.55) it schedules **4 rounds on Phoenix–Dallas only**, costing an expected **85.4 raw pairs** and 0.0568 s to deliver F = 0.5680.
4. ⏳ **Memory-time budgeting** — generation starts are **staggered** so pairs finish together (the routing-layer fix for the naive-schedule decay EntangleNet-Q measured: 0.5022 → 0.3463); pairs then only decay during the purification phase, and that decay is charged before any promise is made. A session whose schedule misses its deadline, or whose delivered fidelity misses its target, gets **NO_ROUTE with the reason** — e.g. target 0.55 in 0.05 s, or target 0.99 at any deadline inside the round cap.
5. 🚦 **Multi-session contention** — links carry one session chain at a time; admission is **earliest-deadline-first**. Of three competing sessions: Phoenix routes at t = 0, Dallas queues behind it on the shared links and still makes its 1.2 s deadline (finish 1.023 s), and Las Vegas → Dallas — perfectly feasible alone — is **QUEUED_HELD** because queueing would push its finish to 1.743 s, past its 1.4 s deadline. The fairness rule is stated in code, not vibes.
6. 💥 **Failure handling** — when the Phoenix–Dallas link drops mid-plan, the session replans over Los Angeles → Las Vegas → Phoenix → Albuquerque → Dallas (2,638 km instead of 2,335 km), reschedules purification, and **survives** at F ≥ 0.55 with ~56.3 expected pairs.
7. 📞 **Classical channel accounting** — every teleported qubit is charged **2 classical bits**, and the schedule includes their one-way light time along the path (2,335 km → a 0.0117 s floor inside the 0.7785 s Dallas schedule). Nothing in this lab is faster than light, and the floor is asserted in CHECKS.
8. 🏷️ **Feasibility classifier** — a from-scratch kNN labels proposed sessions `feasible` / `needs-purification` / `infeasible` from distance + target + deadline features.
9. 🧠 **Advisory seats + checks** — Carbon 4 DECIDER with sha256 trace, Muse advisor, Google Flow plan-only, and a built-in CHECKS suite (47 checks).

## 🗺️ How it works — diagram per script

### `main.py` — the whole lab

```mermaid
flowchart TD
    A[Teleport Request: src / dst / payload / min F / deadline] --> B{Payload gated?}
    B -->|matter / living being| C[HOLD - exit 2]
    B -->|qubit state| D[Path Strategy: fidelity / latency / balanced]
    D --> E[Purification Planner: weakest link first, decay-aware]
    E --> F{Delivered F meets target?}
    F -->|no| G[NO_ROUTE - honest reason]
    F -->|yes| H[Schedule: staggered generation + purify + classical transit]
    H --> I{Inside deadline?}
    I -->|no| G
    I -->|yes| J[EDF Contention Allocator]
    J --> K{Links free in time?}
    K -->|no| L[QUEUED_HELD]
    K -->|yes| M[ROUTED / ROUTED_WITH_PURIFICATION]
    M --> N[CHECKS + VERDICT PROCEED]
```

### `tests/test_main.py` — verification

```mermaid
flowchart LR
    A[pytest] --> B[Physics cross-checks vs EntangleNet-Q]
    A --> C[Strategies + purification planner]
    A --> D[Sessions: routed / NO_ROUTE / HOLD]
    A --> E[Contention + reroute + classifier]
    B --> F[33 passed]
    C --> F
    D --> F
    E --> F
```

### `conftest.py` — test path setup

```mermaid
flowchart LR
    A[conftest.py] --> B[Insert project root into sys.path]
    B --> C[tests import main.py directly]
```

### `Dockerfile` — container

```mermaid
flowchart LR
    A[python:3.12-slim] --> B[COPY project]
    B --> C[CMD python3 main.py demo]
```

## 🤩 Why is this cool?

1. 🛰️ It completes the operator's view of the quantum stack — TeleportX is the protocol, EntangleNet-Q is the physics, this is the **control room**.
2. 🗺️ The latency strategy *loses on purpose*: its shortcut delivers teleport fidelity 0.5912, **below the classical limit** — the lab shows why "fastest" is the wrong default.
3. ✨ Purification is planned against **delivered** fidelity, not fresh — the planner pays the memory-decay tax before promising anything.
4. ⏳ Staggered generation is a real routing-layer win: it erases the wait-decay that cost EntangleNet-Q's naive chain 0.5022 → 0.3463.
5. 🚦 Contention is handled with a stated fairness rule (EDF) and an honest QUEUED_HELD — no silent degradation, no favoritism.
6. 💥 The failure demo doesn't just reroute — it replans purification on the detour and prints the new pair cost.
7. 🚫 Refusals are first-class output: NO_ROUTE comes with the *reason* (deadline, unreachable fidelity), and gated payloads HOLD before any math.
8. 📞 The classical channel is in the schedule, in the budget, and in the checks — the anti-FTL line is arithmetic, not a disclaimer.
9. 🧮 Dijkstra three ways, a greedy planner, EDF allocation, and a kNN — all stdlib `math` and `heapq`. No numpy, no networkx, anywhere.
10. 🎯 Deterministic end to end: run it twice, get byte-identical output — a router you can diff.

## 🛠️ What problems this solves?

1. ❌ **Problem:** Quantum-network demos teleport over perfect pairs on empty networks. ✅ **Solution:** Sessions here carry fidelity targets and deadlines, share links, and can be refused.
2. ❌ **Problem:** Routing demos pick one metric (usually hops) and never show the trade-off. ✅ **Solution:** Three strategies run on the same graph and their delivered fidelity *and* schedule are printed side by side.
3. ❌ **Problem:** Purification is quoted as a fidelity number without cost. ✅ **Solution:** Every plan prices itself in expected raw pairs and seconds before it is accepted.
4. ❌ **Problem:** Plans are made against fresh-pair fidelity that memory decay then destroys. ✅ **Solution:** The planner targets delivered fidelity after decay — and staggered starts remove the generation-wait decay entirely.
5. ❌ **Problem:** "It'll probably be fine" scheduling. ✅ **Solution:** Generation + purification + classical transit are summed and compared to the deadline; misses are NO_ROUTE, in writing.
6. ❌ **Problem:** Shared-resource contention is ignored until production. ✅ **Solution:** A capacity model + EDF admission shows exactly who waits, who makes it, and who gets held — and why.
7. ❌ **Problem:** Failure handling is an afterthought in sim labs. ✅ **Solution:** A dropped link triggers a full replan (path + purification + cost) in the demo and the tests.
8. ❌ **Problem:** Teleportation gets marketed as instant / FTL. ✅ **Solution:** 2 classical bits per qubit are charged at light speed in every schedule, and `claim_ftl_communication` is a permanent HOLD gate.
9. ❌ **Problem:** Session feasibility gets guessed by gut. ✅ **Solution:** A kNN classifier gives a first-pass feasible / needs-purification / infeasible label from the three numbers that matter.
10. ❌ **Problem:** Simulation tools quietly imply a service is next. ✅ **Solution:** 14 named HOLD gates return exit code 2 for every live-operation or production claim, forever.

## 📥 How to install step-by-step

1. 📋 Clone or download this project folder.
2. 🐍 Make sure Python 3.12+ is installed: `python3 --version`
3. ▶️ Run the full demo + checks (no arguments needed):

```bash
python3 main.py
```

4. 🧪 Run the test suite:

```bash
pip install pytest
python3 -m pytest -q
```

5. 🎛️ Try the other commands:

```bash
python3 main.py checks      # 47 built-in checks
python3 main.py strategies  # fidelity vs latency vs balanced, LA -> Dallas
python3 main.py plan        # all demo sessions routed / refused / held
python3 main.py purify      # purification plan for the Dallas session
python3 main.py contention  # EDF allocation of three competing sessions
python3 main.py reroute     # Phoenix-Dallas link drops: the replan
python3 main.py classify    # kNN session feasibility report
python3 main.py brains      # Carbon 4 + Muse + Flow seats
python3 main.py holds       # list all 14 HOLD gates
python3 main.py hold-demo   # exits 2 - gated claims stay HOLD
```

6. 🐳 Or run it in Docker:

```bash
docker build -t credkellar/teleportnet-router:latest .
docker run --rm credkellar/teleportnet-router:latest
```

## 📋 Requirements

- 🐍 Python 3.12 or newer
- 📦 Dependencies: **none** (standard library only)
- 🌐 Network: **none** — fully offline
- 🧪 For tests only: `pytest`
- 🐳 Optional: Docker

## 🧒 5th-grade English section

Imagine a **post office for magic coin pairs**. 📮

- People walk up with a **delivery job**: "Send my tiny message-state from Los Angeles to Dallas. It must arrive *this* clean, and *this* fast." That job is called a **session**. 🧾
- The router is the clerk. First it checks the job is even allowed — nobody may mail a **cat** or a **rock** through the magic post. Those jobs get a big red **HOLD** stamp. 🐱⛔
- Then the clerk picks a **road**. The *cleanest* road is not always the *fastest* road — one shortcut in this lab is so dirty that the delivery arrives worse than sending it the normal way! The clerk shows you all three roads and their prices. 🛣️
- If the pairs on the road are too dirty, the clerk schedules **washes** (purification) on the dirtiest stop first — and counts exactly how many spare pairs and seconds the washes cost *before* saying yes. 🧺
- The clerk also starts each stop's work at just the right time so finished pairs don't sit around **fading** while they wait. Smart timing saves real magic. ⏰
- Sometimes two jobs need the same road at the same time. The job with the **earliest deadline goes first** — that's the fair rule — and if waiting would make a job late, the clerk says so honestly instead of pretending. 🚦
- If a road **closes** mid-job, the clerk finds a detour, re-prices it, and still delivers — or tells you the truth if it can't. 💥
- And no delivery is ever instant: a normal phone call carrying **2 tiny bits** still has to travel with every magic delivery, at light speed. Nothing outruns light — not even magic. 📞

## 🌳 Full file tree

```text
teleportnet-router/
├── main.py                  # the whole lab: physics layer, 3 strategies, purification planner, sessions, contention, reroute, classifier, seats, HOLD gates
├── conftest.py              # puts the project root on sys.path for tests
├── tests/
│   └── test_main.py         # 33 pytest tests: cross-checks, strategies, sessions, contention, reroute, gates, determinism
├── assets/
│   └── cover.png            # README cover image (2736 x 912)
├── Dockerfile               # python:3.12-slim, runs the demo
└── README.md                # this file
```

> 📦 Delivered separately as paste packs (not in this tree): `.github/workflows/ci.yml` + `docker-publish.yml`, and the Docker Hub pack (100-char description, 350-char About, overview, categories).

---

MIT © 2026 Darion Kellar · TeleportNet-Router — educational simulation only 🛰️
