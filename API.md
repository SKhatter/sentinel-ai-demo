# Sentinel.AI — API Reference

> Replace `https://www.agentsentinelai.com` with `http://localhost:3001` if running locally.

**Create a run**
```bash
curl -X POST https://www.agentsentinelai.com/v1/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{"workflow_name": "trip_planner", "input": {"query": "Plan a Japan trip"}}'
```

**Register a contract**
```bash
curl -X POST https://www.agentsentinelai.com/v1/contracts \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "trip_planner",
    "from_step": "planner", "to_step": "research",
    "schema": {
      "type": "object",
      "required": ["destination", "budget", "days"],
      "properties": {
        "destination": {"type": "string"},
        "budget": {"type": "number"},
        "days": {"type": "integer"}
      }
    },
    "on_fail": "block"
  }'
```

**Record a step**
```bash
curl -X POST https://www.agentsentinelai.com/v1/workflows/runs/{run_id}/steps \
  -H "Content-Type: application/json" \
  -d '{"step_name": "planner", "status": "completed",
       "output": {"destination": "Japan", "budget": "two thousand", "days": 5}}'
```

**Replay from checkpoint**
```bash
curl -X POST https://www.agentsentinelai.com/v1/replays \
  -H "Content-Type: application/json" \
  -d '{"run_id": "wf_...", "checkpoint_id": "ckpt_...",
       "patched_output": {"destination": "Japan", "budget": 2000, "days": 5}}'
```

**Get a run**
```bash
curl https://www.agentsentinelai.com/v1/workflows/runs/{run_id}
```

**Get incidents for a run**
```bash
curl https://www.agentsentinelai.com/v1/workflows/runs/{run_id}/incidents
```
