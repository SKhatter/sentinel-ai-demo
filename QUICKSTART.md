# Sentinel.AI — Quickstart

Connect your AI pipeline to the Sentinel dashboard in under 5 minutes.

---

## Step 1 — Install

```bash
pip install sentinelai-sdk
```

Both import names work after installing:

```python
import sentinel      # ✓
import sentinelai   # ✓ also works
```

---

## Step 2 — Get an API key

1. Go to **[www.agentsentinelai.com/dashboard](https://www.agentsentinelai.com/dashboard)**
2. Click the **⚙️ gear icon** in the top-right corner
3. Enter a name for your key (e.g. `my-pipeline`) → click **Generate Key**
4. Copy the `sk_live_...` key — it is shown only once
5. Paste it into Settings → **Save Key** to scope the dashboard to your data

> Free. No credit card required.

---

## Step 3 — Pick your integration pattern

Choose whichever requires the fewest changes to your existing code.

### Option A — Decorator (1 line per function)

Best for standalone agent functions.

```python
import sentinel
sentinel.init(api_key="sk_live_...")

@sentinel.trace_step(name="research-agent", step_type="llm_call", workflow_name="My Pipeline")
def research_agent(query: str) -> dict:
    return my_llm.run(query)   # unchanged
```

---

### Option B — OpenAI auto-patch (2 lines total)

Best for teams using the OpenAI Python SDK. Every `chat.completions.create()` call is traced automatically.

```python
import openai, sentinel
sentinel.init(api_key="sk_live_...")

client = openai.OpenAI(api_key="...")
sentinel.patch_openai(client)                        # ONE LINE
sentinel.set_active_run("run_001", "My Pipeline")

# Everything below is your existing code — completely unchanged
response = client.chat.completions.create(model="gpt-4o", messages=[...])
```

---

### Option C — Anthropic auto-patch (2 lines total)

Best for teams using the Anthropic / Claude SDK.

```python
import anthropic, sentinel
sentinel.init(api_key="sk_live_...")

client = anthropic.Anthropic(api_key="...")
sentinel.patch_anthropic(client)                     # ONE LINE
sentinel.set_active_run("run_001", "My Pipeline")

# Your existing code — unchanged
response = client.messages.create(model="claude-opus-4-6", ...)
```

---

### Option D — LangChain callback (1 line total)

Best for LangChain / LangGraph users. Every LLM call, chain step, and tool use is traced automatically.

```python
import sentinel
sentinel.init(api_key="sk_live_...")

cb = sentinel.LangChainCallback(workflow_name="My Pipeline")  # ONE LINE

# Pass cb to your existing components — nothing else changes
llm   = ChatOpenAI(model="gpt-4o", callbacks=[cb])
chain = LLMChain(llm=llm, prompt=prompt, callbacks=[cb])
result = chain.run("my query")
cb.finish()
```

---

### Option E — Wrap existing code (5–15 lines total)

Best for any existing pipeline where you want full control.

```python
import sentinel
sentinel.init(api_key="sk_live_...")

with sentinel.workflow("My Pipeline") as run:
    with run.step("agent-a", step_type="llm_call") as step:
        step.set_input({"query": "..."})
        result = my_agent_a.run(query)          # unchanged
        step.set_output({"result": result})

    with run.step("agent-b", step_type="tool_call") as step:
        step.set_input({"data": result})
        output = my_agent_b.run(result)         # unchanged
        step.set_output({"output": output})
```

---

## Step 4 — Open the dashboard

Go to **[www.agentsentinelai.com/dashboard](https://www.agentsentinelai.com/dashboard)** after running your pipeline.

| Tab | What you see |
|---|---|
| **Workflows** | Execution DAG: Agent A → B → C |
| **Traces** | Per-step latency, input/output payloads |
| **Incidents** | Auto-created when any step raises an exception |
| **State** | Shared state written by agents |
| **Contracts** | Validated handoffs between agents |

---

## Advanced features

### Agent contracts — enforce schemas at handoff boundaries

```python
sentinel.register_contract(
    agent="agent-b",
    accepts={
        "lead_id": {"type": "string", "required": True},
        "score":   {"type": "number", "min": 0, "max": 1},
    }
)

try:
    sentinel.handoff(from_agent="agent-a", to_agent="agent-b", run_id=run.run_id, payload=result)
except sentinel.ContractViolationError as e:
    print(f"Blocked: {e.violations}")
```

### Shared state — atomic writes, no silent overwrites

```python
# Read
value, version = sentinel.get_state("run_id", "key")

# Write with conflict protection
new_version = sentinel.propose_state("run_id", "key", new_value, base_version=version)

# Auto-retry on conflict
sentinel.propose_state_with_retry("run_id", "key", lambda cur: {**cur, "new_field": "val"})
```

---

## Runnable examples

Working code for each pattern lives in the [`examples/`](examples/) folder:

```bash
python examples/01_decorator.py           --api-key sk_live_...
python examples/02_openai_autopatch.py    --api-key sk_live_... --simulate
python examples/03_anthropic_autopatch.py --api-key sk_live_... --simulate
python examples/04_langchain_callback.py  --api-key sk_live_... --simulate
python examples/05_existing_code_minimal.py --api-key sk_live_... --level all
```

For a full multi-agent demo with contracts, shared state, and handoff validation, see the [main demo README](README.md).

---

*Sentinel.AI — The Control Plane for AI Agents*
*https://www.agentsentinelai.com*
