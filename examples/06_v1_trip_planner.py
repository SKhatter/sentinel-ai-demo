#!/usr/bin/env python3
"""
Integration Pattern 6: v1 API — Contract Validation + Replay
=============================================================
Demonstrates the full v1 flow:

  1. Create a workflow run
  2. Register a contract between planner → research
  3. Planner emits a bad output (budget is a string, not a number)
  4. Sentinel validates the boundary and blocks research
  5. An incident + checkpoint are created automatically
  6. Patch the payload and replay from the checkpoint
  7. Research and executor complete successfully

Best for: teams building new pipelines who want contract enforcement
and structured replay from the start.

Usage:
    python examples/06_v1_trip_planner.py --api-key sk_live_...

    # Against a local server (development only):
    python examples/06_v1_trip_planner.py --api-key sk_live_... --endpoint http://localhost:3001
"""

import argparse
import time
from sentinel import Sentinel

# ── Parse args ──────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser()
parser.add_argument("--api-key",  required=True, help="Sentinel API key (sk_live_...)")
parser.add_argument("--endpoint", default="https://www.agentsentinelai.com",
                    help="Sentinel server URL (default: production)")
args = parser.parse_args()

client = Sentinel(api_key=args.api_key, base_url=args.endpoint)

print("\n" + "="*60)
print("  Sentinel.AI — Trip Planner Demo (v1 API)")
print("="*60)

# ── Step 1: Create workflow run ──────────────────────────────────────────────

print("\n[1] Creating workflow run...")
run = client.start_workflow(
    workflow_name="trip_planner",
    external_run_id="run_demo_001",
    input={"user_query": "Plan a 5-day Japan trip under $2000"},
    metadata={"team": "alpha"}
)
run_id = run["run_id"]
print(f"    run_id  : {run_id}")
print(f"    status  : {run['status']}")

# ── Step 2: Register contract ────────────────────────────────────────────────

print("\n[2] Registering contract: planner → research...")
contract = client.register_contract(
    workflow_name="trip_planner",
    from_step="planner",
    to_step="research",
    schema={
        "type": "object",
        "required": ["destination", "budget", "days"],
        "properties": {
            "destination": {"type": "string"},
            "budget":      {"type": "number", "minimum": 0},
            "days":        {"type": "integer", "minimum": 1}
        }
    },
    on_fail="block"
)
print(f"    contract_id : {contract['contract_id']}")
print(f"    status      : {contract['status']}")

# ── Step 3: Planner emits bad output ────────────────────────────────────────

print("\n[3] Planner running... (budget will be a string — intentional bug)")
time.sleep(0.5)

result = client.record_step(
    run_id=run_id,
    step_name="planner",
    step_type="agent",
    status="completed",
    input={"user_query": "Plan a 5-day Japan trip under $2000"},
    output={
        "destination": "Japan",
        "budget": "two thousand",   # ← wrong type, should be a number
        "days": 5
    }
)

print(f"    step_id : {result['step_id']}")

# ── Step 4: Check boundary result ───────────────────────────────────────────

bc = result.get("boundary_check", {})
if bc.get("result") == "failed":
    print("\n[4] ✗ Boundary check FAILED")
    print(f"    reason      : {bc['reason']}")
    print(f"    blocked     : planner → {bc['blocked_next_step']}")
    print(f"    incident_id : {bc['incident_id']}")
    print(f"    checkpoint  : {bc['checkpoint_id']}")
else:
    print("\n[4] ✓ Boundary check passed (unexpected in this demo)")

# ── Step 5: Inspect run ──────────────────────────────────────────────────────

print("\n[5] Run status after block:")
run_detail = client.get_run(run_id)
print(f"    run status : {run_detail['status']}")
for step in run_detail["steps"]:
    icon = {"completed": "✓", "blocked": "✗", "pending": "·"}.get(step["status"], "·")
    print(f"    {icon} {step['step_name']:<12} {step['status']}")

# ── Step 6: Replay with patched payload ─────────────────────────────────────

print("\n[6] Replaying with corrected payload (budget: 2000)...")
time.sleep(0.5)

replay = client.replay(
    run_id=run_id,
    checkpoint_id=bc["checkpoint_id"],
    patched_output={
        "destination": "Japan",
        "budget": 2000,   # ← fixed
        "days": 5
    }
)

print(f"    replay_run_id      : {replay['replay_run_id']}")
print(f"    status             : {replay['status']}")
print(f"    replayed_from_step : {replay['replayed_from_step']}")

# ── Step 7: Inspect replay run ───────────────────────────────────────────────

print("\n[7] Replay run timeline:")
replay_detail = client.get_run(replay["replay_run_id"])
for step in replay_detail["steps"]:
    icon = {"completed": "✓", "replayed": "↺", "reused": "⟳", "blocked": "✗", "pending": "·"}.get(step["status"], "·")
    print(f"    {icon} {step['step_name']:<12} {step['status']}")

print(f"\n    Final status : {replay_detail['status']}")

print("\n" + "="*60)
print(f"  View at : {args.endpoint.replace('http://localhost:3001', 'https://www.agentsentinelai.com')}/trip-planner")
print("="*60 + "\n")
