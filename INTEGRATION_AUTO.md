# Sentinel.AI — Automatic Integration

The CLI reads your existing pipeline, asks what to add, and writes the instrumented file. No manual API knowledge needed.

> Stuck or need more control? → [Manual Integration](INTEGRATION_MANUAL.md)

---

## Install

```bash
pip install sentinelai-sdk
```

## Get an API key

1. Go to **[www.agentsentinelai.com/dashboard](https://www.agentsentinelai.com/dashboard)**
2. Click the **⚙️ gear icon** → enter a key name → **Generate Key**
3. Copy the `sk_live_...` key — shown only once

> Free. No credit card required.

---

## Run the CLI

```bash
sentinel instrument pipeline.py
```

It finds your functions, asks three questions, and writes `pipeline_sentinel.py`. Your original file is never touched.

---

## 1. Tracing

Records every step — status, latency, inputs, outputs. Dashboard → **Traces** tab.

**Before**
```python
def planner(query):
    return my_llm.run(query)

def research(plan):
    return my_llm.run(plan)

def run_pipeline(query):
    plan   = planner(query)
    result = research(plan)
    return result
```

**CLI**
```
sentinel instrument pipeline.py

Found 3 functions: planner, research, run_pipeline

Your Sentinel API key: sk_live_...
Add tracing? (Y/n): Y
Add contracts? (Y/n): N
Add shared state? (y/N): N

✓ Written to: pipeline_sentinel.py
```

**After** — generated file
```python
import sentinel
sentinel.init(api_key="sk_live_...")

def planner(query):
    return my_llm.run(query)

def research(plan):
    return my_llm.run(plan)

def run_pipeline(query):
    import uuid
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    sentinel.set_active_run(run_id, "my_pipeline")
    plan   = planner(query)
    result = research(plan)
    return result
```

**What you see in the dashboard:** Every step in the **Traces** tab with status, duration, and inputs/outputs.

---

## 2. Contract + Replay

Blocks bad data between agents. If output is invalid, the next agent is blocked, an incident is created, and a checkpoint is saved for replay. Dashboard → **Incidents** tab.

**Before**
```python
def planner(query):
    return my_llm.run(query)   # could return anything

def research(plan):
    return my_llm.run(plan)    # has no idea if plan is valid

def run_pipeline(query):
    plan   = planner(query)
    result = research(plan)
    return result
```

**CLI**
```
sentinel instrument pipeline.py

Found 3 functions: planner, research, run_pipeline

Your Sentinel API key: sk_live_...
Add tracing? (Y/n): Y
Add contracts? (Y/n): Y
  Enforce what 'planner' returns before 'research' runs? (Y/n): Y
  Fields: destination:string, budget:number, days:integer
  ✓ Contract: planner → research
Add shared state? (y/N): N

✓ Written to: pipeline_sentinel.py
```

**After** — generated file
```python
from sentinel import Sentinel
import sentinel
sentinel.init(api_key="sk_live_...")

client = Sentinel(api_key="sk_live_...")
client.register_contract(
    workflow_name="my_pipeline",
    from_step="planner",
    to_step="research",
    schema={
        "type": "object",
        "required": ["destination", "budget", "days"],
        "properties": {
            "destination": {"type": "string", "required": True},
            "budget":      {"type": "number", "required": True},
            "days":        {"type": "integer", "required": True},
        }
    },
    on_fail="block"
)

def planner(query):
    return my_llm.run(query)

def research(plan):
    return my_llm.run(plan)

def run_pipeline(query):
    import uuid
    run_id = f"run_{uuid.uuid4().hex[:10]}"
    sentinel.set_active_run(run_id, "my_pipeline")
    plan = planner(query)
    check = client.record_step(run_id=run_id, step_name="planner", output=plan)
    if check["boundary_check"]["result"] == "failed":
        print("Blocked:", check["boundary_check"]["reason"]); return
    result = research(plan)
    return result
```

**What you see in the dashboard:**

| Step | Bad run | After replay |
|---|---|---|
| planner | completed | replayed |
| research | blocked | completed |

Incidents tab shows: type · reason · blocked transition · checkpoint ID.

---

## 3. Shared State

Safe concurrent writes — no silent overwrites if agents run in parallel. Dashboard → **State** tab.

**Before**
```python
def agent_a(run_id, data):
    result = my_llm.run(data)
    shared_state["output"] = result   # agent_b might overwrite this simultaneously
    return result

def agent_b(run_id, data):
    result = my_llm.run(data)
    shared_state["output"] = result   # silently overwrites agent_a
    return result
```

**CLI**
```
sentinel instrument pipeline.py

Found 2 functions: agent_a, agent_b

Your Sentinel API key: sk_live_...
Add tracing? (Y/n): Y
Add contracts? (Y/n): N
Add shared state? (y/N): Y

✓ Written to: pipeline_sentinel.py
```

**After** — generated file
```python
import sentinel
sentinel.init(api_key="sk_live_...")

def agent_a(run_id, data):
    result = my_llm.run(data)
    sentinel.propose_state_with_retry(run_id, "pipeline_state",
        lambda cur: {**(cur or {}), "result": result})
    return result

def agent_b(run_id, data):
    result = my_llm.run(data)
    sentinel.propose_state_with_retry(run_id, "pipeline_state",
        lambda cur: {**(cur or {}), "result": result})
    return result
```

**What you see in the dashboard:** State tab shows versioned writes from each agent — both writes preserved, no data lost.

---

## All three together

```
sentinel instrument pipeline.py

Add tracing? (Y/n): Y
Add contracts? (Y/n): Y
  Fields: ...
Add shared state? (y/N): Y

✓ Written to: pipeline_sentinel.py
```

The generated file includes all three. → [Full runnable example](pipeline.py)

---

> Stuck or need more control? → [Manual Integration](INTEGRATION_MANUAL.md)
