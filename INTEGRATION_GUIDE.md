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

**Before** — a typical pipeline with no safety checks

```python
def run_pipeline(query):
    plan   = planner(query)     # planner can return anything
    result = research(plan)     # research has no idea if plan is valid
    output = executor(result)
    return output
```

**After** — Sentinel validates the boundary before research ever runs

```python
from sentinel import Sentinel                                          # ← add

client = Sentinel(api_key="sk_live_...")                              # ← add

# Register once — what planner must pass to research                  # ← add
client.register_contract(                                             # ← add
    workflow_name="my_pipeline",                                      # ← add
    from_step="planner",                                              # ← add
    to_step="research",                                               # ← add
    schema={                                                          # ← add
        "type": "object",                                             # ← add
        "required": ["destination", "budget", "days"],                # ← add
        "properties": {                                               # ← add
            "destination": {"type": "string"},                        # ← add
            "budget":      {"type": "number"},                        # ← add
            "days":        {"type": "integer"}                        # ← add
        }                                                             # ← add
    },                                                                # ← add
    on_fail="block"                                                   # ← add
)                                                                     # ← add

def run_pipeline(query):
    run = client.start_workflow(workflow_name="my_pipeline",          # ← add
                                input={"query": query})               # ← add

    plan = planner(query)

    result = client.record_step(                                      # ← add
        run_id=run["run_id"], step_name="planner", output=plan)       # ← add
    if result["boundary_check"]["result"] == "failed":                # ← add
        print("Blocked:", result["boundary_check"]["reason"])         # ← add
        return                                                        # ← add

    result = research(plan)     # only reached if plan is valid
    output = executor(result)
    return output
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
Each pattern shows your **original code** and exactly what changes.

---

### Option A — Decorator (1 line per function)

Best for standalone agent functions. → [full example](examples/01_decorator.py)

**Before**
```python
def planner(query: str) -> dict:
    return my_llm.run(query)

def research(plan: dict) -> dict:
    return my_llm.run(plan)
```

**After** — add 2 lines at the top, 1 decorator per function

```python
import sentinel                                                       # ← add
sentinel.init(api_key="sk_live_...")                                  # ← add

@sentinel.trace_step(name="planner", step_type="llm_call",           # ← add
                     workflow_name="my_pipeline")                     # ← add
def planner(query: str) -> dict:
    return my_llm.run(query)

@sentinel.trace_step(name="research", step_type="llm_call",          # ← add
                     workflow_name="my_pipeline")                     # ← add
def research(plan: dict) -> dict:
    return my_llm.run(plan)
```

---

### Option B — OpenAI auto-patch (2 lines total)

Every `chat.completions.create()` call is traced automatically — no changes to call sites. → [full example](examples/02_openai_autopatch.py)

**Before**
```python
import openai

client = openai.OpenAI(api_key="...")
response = client.chat.completions.create(model="gpt-4o", messages=[...])
```

**After** — add 4 lines, nothing else changes

```python
import openai
import sentinel                                                       # ← add
sentinel.init(api_key="sk_live_...")                                  # ← add

client = openai.OpenAI(api_key="...")
sentinel.patch_openai(client)                                        # ← add
sentinel.set_active_run("run_001", "my_pipeline")                    # ← add

response = client.chat.completions.create(model="gpt-4o", messages=[...])
```

---

### Option C — Anthropic auto-patch (2 lines total)

Same as OpenAI but for Anthropic's SDK. → [full example](examples/03_anthropic_autopatch.py)

**Before**
```python
import anthropic

client = anthropic.Anthropic(api_key="...")
response = client.messages.create(model="claude-opus-4-6", messages=[...])
```

**After** — add 4 lines, nothing else changes

```python
import anthropic
import sentinel                                                       # ← add
sentinel.init(api_key="sk_live_...")                                  # ← add

client = anthropic.Anthropic(api_key="...")
sentinel.patch_anthropic(client)                                     # ← add
sentinel.set_active_run("run_001", "my_pipeline")                    # ← add

response = client.messages.create(model="claude-opus-4-6", messages=[...])
```

---

### Option D — LangChain callback (1 line total)

Every LLM call and chain step is traced automatically. → [full example](examples/04_langchain_callback.py)

**Before**
```python
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain

llm   = ChatOpenAI(model="gpt-4o")
chain = LLMChain(llm=llm, prompt=prompt)
result = chain.run("my query")
```

**After** — add 4 lines, pass `callbacks=[cb]` to existing components

```python
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
import sentinel                                                       # ← add
sentinel.init(api_key="sk_live_...")                                  # ← add

cb = sentinel.LangChainCallback(workflow_name="my_pipeline")         # ← add

llm   = ChatOpenAI(model="gpt-4o", callbacks=[cb])                   # ← add callbacks=[cb]
chain = LLMChain(llm=llm, prompt=prompt, callbacks=[cb])             # ← add callbacks=[cb]
result = chain.run("my query")
cb.finish()                                                          # ← add
```

---

### Option E — Wrap existing code (5–15 lines total)

Full manual control. Best when you want to capture specific inputs/outputs. → [full example](examples/05_existing_code_minimal.py)

**Before**
```python
def run_pipeline(query):
    plan   = planner(query)
    result = research(plan)
    output = executor(result)
    return output
```

**After** — wrap each agent call in `run.step`

```python
import sentinel                                                       # ← add
sentinel.init(api_key="sk_live_...")                                  # ← add

def run_pipeline(query):
    with sentinel.workflow("my_pipeline") as run:                    # ← add
        with run.step("planner", step_type="llm_call") as step:      # ← add
            step.set_input({"query": query})                         # ← add
            plan = planner(query)
            step.set_output({"plan": plan})                          # ← add

        with run.step("research", step_type="llm_call") as step:     # ← add
            step.set_input({"plan": plan})                           # ← add
            result = research(plan)
            step.set_output({"result": result})                      # ← add

        with run.step("executor", step_type="tool_call") as step:    # ← add
            output = executor(result)
            step.set_output({"output": output})                      # ← add

    return output
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
