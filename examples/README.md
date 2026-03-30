# Sentinel.AI — Integration Patterns

Sentinel validates handoffs between agents, blocks unsafe execution, and lets you replay workflows from failure points.

**Start with Contract + Replay** if you want the core product — it's what makes Sentinel different.
Use the tracing patterns below that if you want to instrument an existing pipeline with minimal code changes.

---

## 01 — Contract + Replay (start here)

Agent A emits invalid output → Sentinel blocks Agent B → you patch and replay safely.

This is the core Sentinel flow. Every other pattern adds observability on top of this guarantee.

```python
from sentinel import Sentinel

client = Sentinel(api_key="sk_live_...", base_url="https://www.agentsentinelai.com")

# 1. Start a run
run = client.start_workflow(workflow_name="trip_planner", input={"user_query": "..."})

# 2. Enforce what planner must hand to research
client.register_contract(
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
    }
)

# 3. Planner emits bad output — budget is a string
result = client.record_step(
    run_id=run["run_id"], step_name="planner", status="completed",
    output={"destination": "Japan", "budget": "two thousand", "days": 5}
)

# 4. Sentinel blocked research and created an incident
bc = result["boundary_check"]
# bc["result"]           → "failed"
# bc["reason"]           → '"budget" must be a number'
# bc["blocked_next_step"]→ "research"
# bc["incident_id"]      → "inc_..."
# bc["checkpoint_id"]    → "ckpt_..."

# 5. Patch and replay — research and executor continue from here
replay = client.replay(
    run_id=run["run_id"],
    checkpoint_id=bc["checkpoint_id"],
    patched_output={"destination": "Japan", "budget": 2000, "days": 5}
)
# replay["status"] → "completed"
```

```bash
python examples/06_v1_trip_planner.py --api-key sk_live_...
```

**What you see in the dashboard after this run:**

| | |
|---|---|
| **Blocked transition** | planner → research blocked with reason |
| **Contract violation** | incident created automatically, status: open |
| **Replay run** | new run linked to original, planner: replayed, research: completed |
| **Reused steps** | prior successful steps carried forward, not re-executed |

---

## Tracing patterns — instrument existing code

If you have an existing pipeline and want to add observability, pick whichever pattern requires the fewest changes.

| Pattern | Changes needed | Best for |
|---|---|---|
| [02 — Decorator](#02-decorator) | 1 line per function | Standalone agent functions |
| [03 — OpenAI auto-patch](#03-openai-auto-patch) | 2 lines total | Teams using OpenAI Python SDK |
| [04 — Anthropic auto-patch](#04-anthropic-auto-patch) | 2 lines total | Teams using Anthropic/Claude SDK |
| [05 — LangChain callback](#05-langchain-callback) | 1 line total | LangChain / LangGraph users |
| [06 — Wrap existing code](#06-wrap-existing-code) | 5–15 lines total | Any existing pipeline |

All tracing patterns feed the same dashboard: step latency, input/output payloads, and automatic incidents on failure.

---

## 02 — Decorator

Add `@sentinel.trace_step(...)` above any existing agent function. The function body is untouched.

```python
import sentinel
sentinel.init(api_key="sk_live_...")

@sentinel.trace_step(name="research-agent", step_type="llm_call", workflow_name="My Pipeline")
def research_agent(query: str) -> dict:
    return my_llm.run(query)   # unchanged
```

```bash
python examples/01_decorator.py --api-key sk_live_...
```

---

## 03 — OpenAI Auto-Patch

Call `sentinel.patch_openai(client)` once. Every `client.chat.completions.create()` call is traced automatically.

```python
import openai, sentinel
sentinel.init(api_key="sk_live_...")

client = openai.OpenAI(api_key="...")
sentinel.patch_openai(client)          # ONE LINE
sentinel.set_active_run("run_001", "My Pipeline")

# Everything below is your existing code — completely unchanged
response = client.chat.completions.create(model="gpt-4o", messages=[...])
```

```bash
python examples/02_openai_autopatch.py --api-key sk_live_... --simulate
# With real OpenAI:
python examples/02_openai_autopatch.py --api-key sk_live_... --openai-key sk-...
```

---

## 04 — Anthropic Auto-Patch

Same as OpenAI but for Anthropic's SDK.

```python
import anthropic, sentinel
sentinel.init(api_key="sk_live_...")

client = anthropic.Anthropic(api_key="...")
sentinel.patch_anthropic(client)       # ONE LINE
sentinel.set_active_run("run_001", "My Pipeline")

# Your existing code — unchanged
response = client.messages.create(model="claude-opus-4-6", ...)
```

```bash
python examples/03_anthropic_autopatch.py --api-key sk_live_... --simulate
```

---

## 05 — LangChain Callback

Pass `sentinel.LangChainCallback()` to your LangChain LLMs and chains. Every LLM call, chain step, and tool use is traced automatically.

```python
import sentinel
sentinel.init(api_key="sk_live_...")

cb = sentinel.LangChainCallback(workflow_name="My LangChain Pipeline")  # ONE LINE

# Pass cb to your existing components — nothing else changes
llm   = ChatOpenAI(model="gpt-4o", callbacks=[cb])
chain = LLMChain(llm=llm, prompt=prompt, callbacks=[cb])
result = chain.run("my query")
cb.finish()
```

```bash
python examples/04_langchain_callback.py --api-key sk_live_... --simulate
# With real LangChain + OpenAI:
python examples/04_langchain_callback.py --api-key sk_live_... --openai-key sk-...
```

---

## 06 — Wrap Existing Code

Three levels of effort for wrapping an existing pipeline:

- **Level A** — 5 lines added: wrap everything in `sentinel.workflow()`. Gets you run tracking and failure detection.
- **Level B** — 3 lines per agent: add `run.step()` wrappers. Gets you per-agent latency, DAG, input/output.
- **Level C** — patch at call site: apply decorator without touching function definitions.

```bash
python examples/05_existing_code_minimal.py --api-key sk_live_... --level all
```
