# Sentinel.AI — Integration Examples

Five patterns for connecting Sentinel to your existing code. All produce identical output in the dashboard — pick whichever requires the fewest changes to your codebase.

> New here? Start with the [Quickstart guide](../QUICKSTART.md) first.

---

## Which pattern should I use?

| Pattern | Changes needed | Best for |
|---|---|---|
| [01 — Decorator](#01-decorator) | 1 line per function | Standalone agent functions |
| [02 — OpenAI auto-patch](#02-openai-auto-patch) | 2 lines total | Teams using OpenAI Python SDK |
| [03 — Anthropic auto-patch](#03-anthropic-auto-patch) | 2 lines total | Teams using Anthropic/Claude SDK |
| [04 — LangChain callback](#04-langchain-callback) | 1 line total | LangChain / LangGraph users |
| [05 — Wrap existing code](#05-wrap-existing-code) | 5–15 lines total | Any existing pipeline |
| [06 — v1 API: contract + replay](#06-v1-api-contract--replay) | new pipeline | Contract validation + replay from failure |

---

## 01 — Decorator

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

## 02 — OpenAI Auto-Patch

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

## 03 — Anthropic Auto-Patch

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

## 04 — LangChain Callback

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

## 05 — Wrap Existing Code

Three levels of effort for wrapping an existing pipeline:

- **Level A** — 5 lines added: wrap everything in `sentinel.workflow()`. Gets you run tracking and failure detection.
- **Level B** — 3 lines per agent: add `run.step()` wrappers. Gets you per-agent latency, DAG, input/output.
- **Level C** — patch at call site: apply decorator without touching function definitions.

```bash
python examples/05_existing_code_minimal.py --api-key sk_live_... --level all
```

---

---

## 06 — v1 API: Contract + Replay

Uses the `Sentinel` client class. Demonstrates the full contract validation and replay flow:
planner emits a bad payload → research is blocked → incident created → patch and replay.

```python
from sentinel import Sentinel

client = Sentinel(api_key="sk_live_...", base_url="https://www.agentsentinelai.com")

run = client.start_workflow(workflow_name="trip_planner", input={"user_query": "..."})

client.register_contract(
    workflow_name="trip_planner",
    from_step="planner",
    to_step="research",
    schema={"type": "object", "required": ["destination", "budget", "days"], "properties": {
        "destination": {"type": "string"},
        "budget": {"type": "number", "minimum": 0},
        "days": {"type": "integer", "minimum": 1}
    }}
)

result = client.record_step(run_id=run["run_id"], step_name="planner", status="completed",
    output={"destination": "Japan", "budget": "two thousand", "days": 5})

if result.get("boundary_check", {}).get("result") == "failed":
    replay = client.replay(
        run_id=run["run_id"],
        checkpoint_id=result["boundary_check"]["checkpoint_id"],
        patched_output={"destination": "Japan", "budget": 2000, "days": 5}
    )
```

```bash
python examples/06_v1_trip_planner.py --api-key sk_live_...
# Against local server:
python examples/06_v1_trip_planner.py --api-key sk_live_... --endpoint http://localhost:3001
```

---

## What appears in the dashboard

| Dashboard tab | What you see |
|---|---|
| **Workflows** | Execution DAG: Agent A → B → C → D |
| **Traces** | Per-step latency, input/output payloads |
| **Incidents** | Auto-created when any step raises an exception |
| **State** | Shared state written by agents (if using `sentinel.propose_state`) |
| **Contracts** | Validated handoffs between agents (if using `sentinel.handoff`) |
