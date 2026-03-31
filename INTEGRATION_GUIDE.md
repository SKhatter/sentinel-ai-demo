# Sentinel.AI — Integration Guide

## Install

```bash
pip install sentinelai-sdk
```

```python
import sentinel      # ✓
import sentinelai   # ✓ also works
```

## Get an API key

1. Go to **[www.agentsentinelai.com/dashboard](https://www.agentsentinelai.com/dashboard)**
2. Click the **⚙️ gear icon** → enter a key name → **Generate Key**
3. Copy the `sk_live_...` key — shown only once
4. Paste it into Settings → **Save Key**

> Free. No credit card required.

---

## Pick what you need

| I want to… | Feature | Dashboard tab |
|---|---|---|
| See what my agents are doing — steps, inputs, outputs, latency | **Tracing** | Traces |
| Block bad data from reaching the next agent, replay from failure | **Contract + Replay** | Incidents |
| Let concurrent agents write shared state without overwriting each other | **Shared State** | State |

---

## 1. Tracing — See what your agents are doing

Adds step-by-step visibility. Nothing is blocked. Dashboard → **Traces** tab.

> Lines starting with `+` are new. Copy without the `+`.

### Option A — Decorator (1 line per function)

→ [full example](examples/01_decorator.py)

**Before**
```python
def planner(query: str) -> dict:
    return my_llm.run(query)

def research(plan: dict) -> dict:
    return my_llm.run(plan)
```

**After**
```diff
+import sentinel
+sentinel.init(api_key="sk_live_...")
+
+@sentinel.trace_step(name="planner", step_type="llm_call", workflow_name="my_pipeline")
 def planner(query: str) -> dict:
     return my_llm.run(query)

+@sentinel.trace_step(name="research", step_type="llm_call", workflow_name="my_pipeline")
 def research(plan: dict) -> dict:
     return my_llm.run(plan)
```

---

### Option B — OpenAI auto-patch (4 lines total)

Every `chat.completions.create()` call is traced automatically. → [full example](examples/02_openai_autopatch.py)

**Before**
```python
import openai

client = openai.OpenAI(api_key="...")
response = client.chat.completions.create(model="gpt-4o", messages=[...])
```

**After**
```diff
 import openai
+import sentinel
+sentinel.init(api_key="sk_live_...")

 client = openai.OpenAI(api_key="...")
+sentinel.patch_openai(client)          # all calls traced from here
+sentinel.set_active_run("run_001", "my_pipeline")

 response = client.chat.completions.create(model="gpt-4o", messages=[...])
```

---

### Option C — Anthropic auto-patch (4 lines total)

→ [full example](examples/03_anthropic_autopatch.py)

**Before**
```python
import anthropic

client = anthropic.Anthropic(api_key="...")
response = client.messages.create(model="claude-opus-4-6", messages=[...])
```

**After**
```diff
 import anthropic
+import sentinel
+sentinel.init(api_key="sk_live_...")

 client = anthropic.Anthropic(api_key="...")
+sentinel.patch_anthropic(client)       # all calls traced from here
+sentinel.set_active_run("run_001", "my_pipeline")

 response = client.messages.create(model="claude-opus-4-6", messages=[...])
```

---

### Option D — LangChain callback (4 lines total)

→ [full example](examples/04_langchain_callback.py)

**Before**
```python
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain

llm   = ChatOpenAI(model="gpt-4o")
chain = LLMChain(llm=llm, prompt=prompt)
result = chain.run("my query")
```

**After**
```diff
 from langchain.chat_models import ChatOpenAI
 from langchain.chains import LLMChain
+import sentinel
+sentinel.init(api_key="sk_live_...")

+cb = sentinel.LangChainCallback(workflow_name="my_pipeline")

-llm   = ChatOpenAI(model="gpt-4o")
-chain = LLMChain(llm=llm, prompt=prompt)
+llm   = ChatOpenAI(model="gpt-4o", callbacks=[cb])
+chain = LLMChain(llm=llm, prompt=prompt, callbacks=[cb])
 result = chain.run("my query")
+cb.finish()
```

---

### Option E — Wrap existing code (5–15 lines total)

Full control over what inputs/outputs are captured. → [full example](examples/05_existing_code_minimal.py)

**Before**
```python
def run_pipeline(query):
    plan   = planner(query)
    result = research(plan)
    output = executor(result)
    return output
```

**After**
```diff
+import sentinel
+sentinel.init(api_key="sk_live_...")

 def run_pipeline(query):
-    plan   = planner(query)
-    result = research(plan)
-    output = executor(result)
+    with sentinel.workflow("my_pipeline") as run:
+        with run.step("planner", step_type="llm_call") as step:
+            step.set_input({"query": query})
+            plan = planner(query)
+            step.set_output({"plan": plan})
+
+        with run.step("research", step_type="llm_call") as step:
+            step.set_input({"plan": plan})
+            result = research(plan)
+            step.set_output({"result": result})
+
+        with run.step("executor", step_type="tool_call") as step:
+            output = executor(result)
+            step.set_output({"output": output})
+
     return output
```

---

## 2. Contract + Replay — Block bad data, recover from failure

Define what one agent must hand to the next. If the output is invalid, Sentinel blocks the downstream agent, creates an incident, and saves a checkpoint so you can fix and replay — without re-running the whole pipeline.

Dashboard → **Incidents** tab · [Live demo](https://www.agentsentinelai.com/trip-planner)

> Lines starting with `+` are new. Copy without the `+`.

**Before**
```python
def run_pipeline(query):
    plan   = planner(query)
    result = research(plan)
    output = executor(result)
    return output
```

**After**
```diff
+from sentinel import Sentinel
+
+client = Sentinel(api_key="sk_live_...")
+
+client.register_contract(        # define what planner must hand to research
+    workflow_name="my_pipeline",
+    from_step="planner",
+    to_step="research",
+    schema={
+        "type": "object",
+        "required": ["destination", "budget", "days"],
+        "properties": {
+            "destination": {"type": "string"},
+            "budget":      {"type": "number"},
+            "days":        {"type": "integer"}
+        }
+    },
+    on_fail="block"
+)
+
 def run_pipeline(query):
+    run = client.start_workflow(workflow_name="my_pipeline", input={"query": query})
+
     plan = planner(query)
+
+    result = client.record_step(run_id=run["run_id"], step_name="planner", output=plan)
+    if result["boundary_check"]["result"] == "failed":   # Sentinel blocked research
+        print("Blocked:", result["boundary_check"]["reason"])
+        return
+
     result = research(plan)
     output = executor(result)
     return output
```

**What you see in the dashboard:**

| Step | Bad run | After replay |
|---|---|---|
| planner | completed | replayed |
| research | blocked | completed |
| executor | pending | completed |

Incidents tab shows: type · reason · blocked transition · checkpoint ID.

→ [Runnable example](examples/06_v1_trip_planner.py)

---

## 3. Shared State — Safe concurrent writes

Multiple agents writing the same key simultaneously without data loss. Uses optimistic locking — each write includes the version it read; conflicts are detected and retried.

Dashboard → **State** tab

**Before** — two agents race to update the same key; one write is silently lost
```python
state["lead"] = {"score": 0.87}       # agent-a
state["lead"] = {"tone": "positive"}  # agent-b — overwrites agent-a
```

**After**
```python
# agent-a
value, version = sentinel.get_state(run_id, "lead")
sentinel.propose_state(run_id, "lead", {"score": 0.87}, base_version=version)

# agent-b — auto-retries if agent-a wrote first, merges instead of overwriting
sentinel.propose_state_with_retry(run_id, "lead", lambda cur: {**cur, "tone": "positive"})
```

→ [Runnable example](examples/demo_state_conflict.py)

---

## Run Locally

```bash
git clone https://github.com/SKhatter/sentinel-ai.git
cd sentinel-ai && npm install && node server.js
# → http://localhost:3001
```

Data resets on restart. The hosted dashboard at [agentsentinelai.com](https://www.agentsentinelai.com) persists via Redis.

---

*Sentinel.AI — The Control Plane for AI Agents · https://www.agentsentinelai.com*
