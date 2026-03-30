# Sentinel.AI — Integration Guide

## What Sentinel Actually Does

Sentinel helps teams run AI agent workflows safely.

Instead of just showing what happened, Sentinel:

- validates state passed between agents
- blocks unsafe execution
- surfaces the root cause
- lets you replay from the exact failure point

**Tracing shows the path. It does not prevent bad execution.**

---

## Install

```bash
pip install sentinelai-sdk
```

Both import names work:

```python
import sentinel      # ✓
import sentinelai   # ✓ also works
```

---

## Get an API key

1. Go to **[www.agentsentinelai.com/dashboard](https://www.agentsentinelai.com/dashboard)**
2. Click the **⚙️ gear icon** → enter a key name → **Generate Key**
3. Copy the `sk_live_...` key — shown only once
4. Paste it into Settings → **Save Key** to scope the dashboard to your data

> Free. No credit card required.

---

## The Core Workflow — Start Here

### Contract + Replay

Agent A emits invalid state → Sentinel blocks Agent B → you patch and replay safely.

This is the most important integration. Use the tracing patterns below if you want to instrument an existing pipeline on top of this.

```python
from sentinel import Sentinel

client = Sentinel(api_key="sk_live_...")

# 1. Start workflow
run = client.start_workflow(
    workflow_name="trip_planner",
    input={"query": "Plan a Japan trip under $2000"}
)

# 2. Register contract between agents
client.register_contract(
    workflow_name="trip_planner",
    from_step="planner",
    to_step="research",
    schema={
        "type": "object",
        "required": ["destination", "budget", "days"],
        "properties": {
            "destination": {"type": "string"},
            "budget":      {"type": "number"},
            "days":        {"type": "integer"}
        }
    },
    on_fail="block"
)

# 3. Planner produces invalid state
result = client.record_step(
    run_id=run["run_id"],
    step_name="planner",
    output={
        "destination": "Japan",
        "budget": "two thousand",  # invalid — should be a number
        "days": 5
    }
)

# 4. Sentinel blocks downstream execution
if result["boundary_check"]["result"] == "failed":
    print("Blocked:", result["boundary_check"]["reason"])

    # 5. Fix and replay
    replay = client.replay(
        run_id=run["run_id"],
        checkpoint_id=result["boundary_check"]["checkpoint_id"],
        patched_output={"destination": "Japan", "budget": 2000, "days": 5}
    )
    print(replay["status"])  # completed
```

→ [Runnable example](examples/06_v1_trip_planner.py)

**What happens:**

```
Planner → invalid output → BLOCK
              ↓
         Fix + Replay
              ↓
Research → Executor → Success
```

**What you see in the dashboard:**

| | Before replay | After replay |
|---|---|---|
| planner | completed | replayed |
| research | blocked | completed |
| executor | pending | completed |

Incidents tab shows: `contract_violation` · reason · blocked transition · checkpoint ID.

---

## Tracing Patterns — Instrument Existing Code

Use these to add observability to a pipeline you already have.
All patterns produce the same output: step latency, input/output payloads, automatic incidents on failure.

---

### Option A — Decorator (1 line per function)

Best for standalone agent functions. → [full example](examples/01_decorator.py)

```python
import sentinel
sentinel.init(api_key="sk_live_...")

@sentinel.trace_step(name="planner", step_type="llm_call", workflow_name="trip_planner")
def planner(query: str) -> dict:
    return my_llm.run(query)   # unchanged
```

---

### Option B — OpenAI auto-patch (2 lines total)

Every `chat.completions.create()` call is traced automatically. → [full example](examples/02_openai_autopatch.py)

```python
import openai, sentinel
sentinel.init(api_key="sk_live_...")

client = openai.OpenAI(api_key="...")
sentinel.patch_openai(client)          # ONE LINE
sentinel.set_active_run("run_001", "trip_planner")

response = client.chat.completions.create(model="gpt-4o", messages=[...])
```

---

### Option C — Anthropic auto-patch (2 lines total)

Same as OpenAI but for Anthropic's SDK. → [full example](examples/03_anthropic_autopatch.py)

```python
import anthropic, sentinel
sentinel.init(api_key="sk_live_...")

client = anthropic.Anthropic(api_key="...")
sentinel.patch_anthropic(client)       # ONE LINE
sentinel.set_active_run("run_001", "trip_planner")

response = client.messages.create(model="claude-opus-4-6", ...)
```

---

### Option D — LangChain callback (1 line total)

Every LLM call, chain step, and tool use is traced automatically. → [full example](examples/04_langchain_callback.py)

```python
import sentinel
sentinel.init(api_key="sk_live_...")

cb = sentinel.LangChainCallback(workflow_name="trip_planner")  # ONE LINE

llm   = ChatOpenAI(model="gpt-4o", callbacks=[cb])
chain = LLMChain(llm=llm, prompt=prompt, callbacks=[cb])
result = chain.run("my query")
cb.finish()
```

---

### Option E — Wrap existing code (5–15 lines total)

Full manual control over what gets traced. → [full example](examples/05_existing_code_minimal.py)

```python
import sentinel
sentinel.init(api_key="sk_live_...")

with sentinel.workflow("trip_planner") as run:
    with run.step("planner", step_type="llm_call") as step:
        step.set_input({"query": "..."})
        result = planner.run(query)        # unchanged
        step.set_output({"result": result})

    with run.step("research", step_type="llm_call") as step:
        step.set_input({"plan": result})
        output = research.run(result)      # unchanged
        step.set_output({"output": output})
```

---

## Advanced — Shared State

Atomic writes across concurrent agents — no silent overwrites.

```python
# Read
value, version = sentinel.get_state("run_id", "key")

# Write with conflict protection
new_version = sentinel.propose_state("run_id", "key", new_value, base_version=version)

# Auto-retry on conflict
sentinel.propose_state_with_retry("run_id", "key", lambda cur: {**cur, "new_field": "val"})
```

---

## Curl Reference

**Create a workflow run**
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

**Emit a step**
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

> Replace `https://www.agentsentinelai.com` with `http://localhost:3001` if running locally.

---

## When To Use Sentinel

Use Sentinel if:

- you run multi-step agent workflows
- agents pass structured state to each other
- failures happen several steps later
- you want to prevent bad execution, not just debug it

You don't need Sentinel if:

- you only run single LLM calls
- workflows are simple and stateless
- failures don't have downstream side effects

---

## Run Locally

```bash
git clone https://github.com/SKhatter/sentinel-ai.git
cd sentinel-ai && npm install && node server.js
# → http://localhost:3001
```

Data is in-memory when running locally — resets on restart. The hosted dashboard at [agentsentinelai.com](https://www.agentsentinelai.com) persists data via Redis.

---

*Sentinel.AI — The Control Plane for AI Agents · https://www.agentsentinelai.com*
