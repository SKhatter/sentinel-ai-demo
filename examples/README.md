# Sentinel.AI — Integration Examples

Pick the pattern that fits your existing code. All patterns produce identical
output in the dashboard — use whichever requires the fewest changes to your codebase.

---

## Which pattern should I use?

| Pattern | Changes needed | Best for |
|---|---|---|
| [01 — Decorator](#01-decorator) | 1 line per function | Standalone agent functions |
| [02 — OpenAI auto-patch](#02-openai-auto-patch) | 2 lines total | Teams using OpenAI Python SDK |
| [03 — Anthropic auto-patch](#03-anthropic-auto-patch) | 2 lines total | Teams using Anthropic/Claude SDK |
| [04 — LangChain callback](#04-langchain-callback) | 1 line total | LangChain / LangGraph users |
| [05 — Wrap existing code](#05-wrap-existing-code) | 5–15 lines total | Any existing pipeline |

---

## Install

```bash
pip install sentinelai-sdk
```

After installing, both import names work:

```python
import sentinel      # ✓
import sentinelai   # ✓ also works
```

## Get an API key

1. Go to **[www.agentsentinelai.com/dashboard](https://www.agentsentinelai.com/dashboard)**
2. Click the **⚙️ gear icon** → enter a key name → **Generate Key**
3. Copy the `sk_live_...` key — shown only once
4. Paste it back into Settings → **Save Key** to scope the dashboard to your data

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

## What appears in the dashboard

All patterns produce the same dashboard output:

| Dashboard tab | What you see |
|---|---|
| **Workflows** | Execution DAG: Agent A → B → C → D |
| **Traces** | Per-step latency, input/output payloads |
| **Incidents** | Auto-created when any step raises an exception |
| **State** | Shared state written by agents (if using `sentinel.propose_state`) |
| **Contracts** | Validated handoffs between agents (if using `sentinel.handoff`) |
