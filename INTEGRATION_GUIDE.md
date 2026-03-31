# Sentinel.AI — Integration Guide

## Install

```bash
pip install sentinelai-sdk
```

## Get an API key

1. Go to **[www.agentsentinelai.com/dashboard](https://www.agentsentinelai.com/dashboard)**
2. Click the **⚙️ gear icon** → enter a key name → **Generate Key**
3. Copy the `sk_live_...` key — shown only once
4. Paste it into Settings → **Save Key**

> Free. No credit card required.

---

## Quickest way to get started — CLI

Run this on your existing pipeline file. It asks what you want to add and writes the instrumented version.

```bash
sentinel instrument pipeline.py
```

```
Analyzing pipeline.py...

Found 4 functions: planner, research, executor, run_pipeline

Your Sentinel API key: sk_live_...

Add tracing? (Y/n): Y

Add contracts? (Y/n): Y
  Enforce what 'planner' returns before 'research' runs? (Y/n): Y
  Fields: destination:string, budget:number, days:integer
  ✓ Contract: planner → research

Do agents run concurrently? Add shared state? (y/N): N

✓ Written to: pipeline_sentinel.py
```

Writes `pipeline_sentinel.py` — your original file is never overwritten. Review and rename when ready.

Covers all three features: **tracing**, **contracts**, and **shared state**.

---

## What Sentinel adds

| Feature | What it does | Dashboard tab |
|---|---|---|
| **Tracing** | Records every step — status, latency, inputs, outputs | Traces |
| **Contract + Replay** | Blocks bad data between agents, saves checkpoint to replay from | Incidents |
| **Shared State** | Safe concurrent writes — no silent overwrites between parallel agents | State |

These stack — use one, two, or all three.

---

## 1. Tracing — See what your agents are doing

**Use when:** you want to observe a pipeline — debug failures, measure latency, inspect what each agent received and returned.

**Skip when:** you only make single LLM calls with no pipeline structure.

> Lines starting with `+` are new. Copy without the `+`.

### Option A — auto_instrument() — zero changes, tracing only

One line. Detects openai, anthropic, langchain and patches them automatically. → [full example](examples/07_auto_instrument.py)

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
+sentinel.auto_instrument(api_key="sk_live_...")   # detects openai, patches automatically
+sentinel.set_active_run("run_001", "my_pipeline")

 client = openai.OpenAI(api_key="...")
 response = client.chat.completions.create(model="gpt-4o", messages=[...])
```

> Want contracts and shared state too? Use `sentinel instrument pipeline.py` instead.

---

### Option B — Decorator (1 line per function)

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

### Option C — OpenAI auto-patch

→ [full example](examples/02_openai_autopatch.py)

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
+sentinel.patch_openai(client)
+sentinel.set_active_run("run_001", "my_pipeline")

 response = client.chat.completions.create(model="gpt-4o", messages=[...])
```

---

### Option D — Anthropic auto-patch

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
+sentinel.patch_anthropic(client)
+sentinel.set_active_run("run_001", "my_pipeline")

 response = client.messages.create(model="claude-opus-4-6", messages=[...])
```

---

### Option E — LangChain callback

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

### Option F — Wrap existing code

→ [full example](examples/05_existing_code_minimal.py)

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

**Use when:** agents pass structured data to each other and a bad payload reaching the next agent causes real damage — wasted compute, wrong emails sent, corrupted state.

**Skip when:** agents are independent, don't hand off structured data, or failures are cheap to re-run from scratch.

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

→ [Runnable example](examples/06_v1_trip_planner.py)

---

## 3. Shared State — Safe concurrent writes

**Use when:** two or more agents run in parallel and write to the same key.

**Skip when:** agents run sequentially — no concurrent writes, no conflict possible.

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

## Using all three together

The recommended path: run `sentinel instrument pipeline.py` — it asks what you need and generates everything.

Or add manually:

> Replace `agent_a / agent_b / agent_c` with your agent names.
> Replace field names in contracts with what your agent actually expects to receive.

**Before**
```python
def run_pipeline(run_id, input_data):
    output_a = agent_a(input_data)
    output_b = agent_b(output_a)
    result   = agent_c(output_b)
    return result
```

**After**
```diff
+from sentinel import Sentinel
+import sentinel
+sentinel.init(api_key="sk_live_...")
+
+client = Sentinel(api_key="sk_live_...")
+client.register_contract(agent="agent_b", accepts={   # fields agent_b expects
+    "field_1": {"type": "string", "required": True},
+    "field_2": {"type": "number", "required": True},
+})
+client.register_contract(agent="agent_c", accepts={   # fields agent_c expects
+    "field_3": {"type": "string", "required": True},
+    "field_4": {"type": "number", "required": True},
+})

 def run_pipeline(run_id, input_data):
+    import uuid; run_id = f"run_{uuid.uuid4().hex[:10]}"
+    with sentinel.workflow("my_pipeline", run_id=run_id) as run:
+
+        with run.step("agent_a", step_type="llm_call") as step:   # Tracing
+            step.set_input(input_data)
+            output_a = agent_a(input_data)
+            step.set_output(output_a)
+            sentinel.propose_state_with_retry(run_id, "pipeline_state",  # Shared State
+                lambda cur: {**(cur or {}), "agent_a_output": output_a})
+
+        client.record_step(run_id=run_id, step_name="agent_a", output=output_a)  # Contract check
+
+        with run.step("agent_b", step_type="llm_call") as step:   # Tracing
+            prior, _ = sentinel.get_state(run_id, "pipeline_state")  # Shared State
+            step.set_input(output_a)
+            output_b = agent_b(output_a)
+            step.set_output(output_b)
+
+        client.record_step(run_id=run_id, step_name="agent_b", output=output_b)  # Contract check
+
+        with run.step("agent_c", step_type="llm_call") as step:   # Tracing
+            step.set_input(output_b)
+            result = agent_c(output_b)
+            step.set_output(result)
+            sentinel.propose_state_with_retry(run_id, "pipeline_state",  # Shared State
+                lambda cur: {**(cur or {}), "final_result": result})
+
-    output_a = agent_a(input_data)
-    output_b = agent_b(output_a)
-    result   = agent_c(output_b)
     return result
```

**What you see in the dashboard:**

| Tab | What appears |
|---|---|
| **Traces** | Every step — status, latency, inputs, outputs |
| **Incidents** | Any blocked handoff — reason, violated field, checkpoint to replay from |
| **State** | Versioned writes from each agent — no data lost even if two agents write at once |

→ [Full runnable example](pipeline.py)

```bash
python pipeline.py --api-key sk_live_...
```

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
