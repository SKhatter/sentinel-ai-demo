# Sentinel.AI — v1 API Quickstart

Contract validation · blocked execution · replay from failure.

This guide shows one concrete flow:
1. A workflow step emits output
2. Sentinel validates the boundary to the next step
3. Sentinel blocks downstream execution if the payload is invalid
4. Sentinel creates an incident and checkpoint
5. You patch the payload and replay from that boundary

---

## Install

```bash
pip install sentinelai-sdk
```

---

## Start a workflow run

```python
from sentinel import Sentinel

client = Sentinel(api_key="sk_live_...", base_url="https://www.agentsentinelai.com")

run = client.start_workflow(
    workflow_name="trip_planner",
    input={"user_query": "Plan a 5-day Japan trip under $2000"}
)
print(run["run_id"])  # wf_abc123...
```

```bash
curl -X POST https://www.agentsentinelai.com/v1/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "trip_planner",
    "external_run_id": "run_123",
    "input": {"user_query": "Plan a 5-day Japan trip under $2000"}
  }'
```

---

## Register a contract between steps

```python
client.register_contract(
    workflow_name="trip_planner",
    from_step="planner",
    to_step="research",
    schema={
        "type": "object",
        "required": ["destination", "budget", "days"],
        "properties": {
            "destination": {"type": "string"},
            "budget": {"type": "number", "minimum": 0},
            "days": {"type": "integer", "minimum": 1}
        }
    },
    on_fail="block"
)
```

```bash
curl -X POST https://www.agentsentinelai.com/v1/contracts \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "trip_planner",
    "from_step": "planner",
    "to_step": "research",
    "schema": {
      "type": "object",
      "required": ["destination", "budget", "days"],
      "properties": {
        "destination": {"type": "string"},
        "budget": {"type": "number", "minimum": 0},
        "days": {"type": "integer", "minimum": 1}
      }
    },
    "on_fail": "block"
  }'
```

---

## Record a step (triggers boundary check)

The `budget` field is a string — this will fail the contract.

```python
result = client.record_step(
    run_id=run["run_id"],
    step_name="planner",
    step_type="agent",
    status="completed",
    input={"user_query": "Plan a 5-day Japan trip under $2000"},
    output={"destination": "Japan", "budget": "two thousand", "days": 5}
)

print(result["boundary_check"])
# {
#   "result": "failed",
#   "contract_id": "ct_001",
#   "reason": '"budget" must be a number',
#   "blocked_next_step": "research",
#   "incident_id": "inc_001",
#   "checkpoint_id": "ckpt_001"
# }
```

```bash
curl -X POST https://www.agentsentinelai.com/v1/workflows/runs/wf_abc123/steps \
  -H "Content-Type: application/json" \
  -d '{
    "step_name": "planner",
    "step_type": "agent",
    "status": "completed",
    "output": {"destination": "Japan", "budget": "two thousand", "days": 5}
  }'
```

---

## List incidents for a run

```python
incidents = client.get_incidents(run["run_id"])
for inc in incidents:
    print(inc["reason"], "→ checkpoint:", inc["checkpoint_id"])
```

```bash
curl https://www.agentsentinelai.com/v1/workflows/runs/wf_abc123/incidents
```

---

## Replay from checkpoint

Patch the payload and resume. Prior successful steps are reused automatically.

```python
if result.get("boundary_check", {}).get("result") == "failed":
    bc = result["boundary_check"]
    replay = client.replay(
        run_id=run["run_id"],
        checkpoint_id=bc["checkpoint_id"],
        patched_output={"destination": "Japan", "budget": 2000, "days": 5}
    )
    print(replay)
    # {"replay_run_id": "wf_abc123_r1", "status": "completed", "replayed_from_step": "planner"}
```

```bash
curl -X POST https://www.agentsentinelai.com/v1/replays \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": "wf_abc123",
    "checkpoint_id": "ckpt_001",
    "patched_output": {"destination": "Japan", "budget": 2000, "days": 5}
  }'
```

---

## Get run status + timeline

```python
run_detail = client.get_run(run["run_id"])
for step in run_detail["steps"]:
    print(step["step_name"], "→", step["status"])
# planner  → completed
# research → blocked
# executor → pending
```

```bash
curl https://www.agentsentinelai.com/v1/workflows/runs/wf_abc123
```

---

## Full Python example

```python
from sentinel import Sentinel

client = Sentinel(api_key="sk_live_...", base_url="https://www.agentsentinelai.com")

# 1. Create run
run = client.start_workflow(
    workflow_name="trip_planner",
    input={"user_query": "Plan a 5-day Japan trip under $2000"}
)

# 2. Register contract
client.register_contract(
    workflow_name="trip_planner",
    from_step="planner",
    to_step="research",
    schema={
        "type": "object",
        "required": ["destination", "budget", "days"],
        "properties": {
            "destination": {"type": "string"},
            "budget": {"type": "number", "minimum": 0},
            "days": {"type": "integer", "minimum": 1}
        }
    }
)

# 3. Planner emits bad output (budget is a string)
result = client.record_step(
    run_id=run["run_id"],
    step_name="planner",
    output={"destination": "Japan", "budget": "two thousand", "days": 5}
)

# 4. Sentinel blocks research, creates incident
bc = result.get("boundary_check", {})
if bc.get("result") == "failed":
    print("Blocked:", bc["reason"])
    print("Incident:", bc["incident_id"])

    # 5. Patch and replay
    replay = client.replay(
        run_id=run["run_id"],
        checkpoint_id=bc["checkpoint_id"],
        patched_output={"destination": "Japan", "budget": 2000, "days": 5}
    )
    print("Replay run:", replay["replay_run_id"], "→", replay["status"])
```

---

## Interactive demo

Open **https://www.agentsentinelai.com/trip-planner** to see the workflow timeline, incident panel, and replay UI in action.

---

*Sentinel.AI — The Control Plane for AI Agents*
