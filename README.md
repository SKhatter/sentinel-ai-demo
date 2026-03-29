# Sentinel.AI — Demo: Customer Outreach Pipeline

This repository simulates an **external customer** using [Sentinel.AI](https://agentsentinelai.com) to observe, coordinate, and protect a 3-agent AI workflow.

No prior knowledge of Sentinel's internals is needed — you only use the public API and the single-file SDK.

---

## What this demo shows

| Feature | Where to see it |
|---|---|
| Workflow + step tracing | Dashboard → **Traces** tab |
| Atomic shared state (concurrent writes, no lost data) | Dashboard → **State** tab |
| Agent contracts (schema enforcement at handoff boundaries) | Dashboard → **Contracts** tab |
| Handoff validation (bad payload blocked before delivery) | `demo_bad_handoff.py` output + Dashboard → Incidents |
| State conflict + safe merge | `demo_state_conflict.py` output |
| Automatic incident on step failure | Dashboard → **Incidents** tab |

---

## The 3-Agent Pipeline

```
   ┌─────────────────┐        handoff       ┌──────────────────────┐        handoff       ┌───────────────┐
   │  Research Agent │  ─────────────────►  │  Personalize Agent   │  ─────────────────►  │ Deliver Agent │
   │                 │                      │                      │                      │               │
   │  • Scores leads │    validated by      │  • Reads lead from   │    validated by      │  • Sends email│
   │  • Writes best  │    Sentinel before   │    shared state      │    Sentinel before   │  • Records    │
   │    lead to      │    delivery          │  • Generates email   │    delivery          │    outcome in │
   │    shared state │                      │    draft             │                      │    shared     │
   └─────────────────┘                      └──────────────────────┘                      │    state      │
                                                                                          └───────────────┘
```

All agent activity, state changes, and handoffs flow through Sentinel and appear live in the dashboard.

---

## Prerequisites

- Python 3.8+
- No pip packages required — the SDK is a single file (`sentinel_sdk.py`)

---

## Step 1 — Get an API key

```bash
curl -X POST https://agentsentinelai.com/api/keys \
  -H "Content-Type: application/json" \
  -d '{"name": "my-outreach-demo"}'
```

Response:
```json
{ "key": "sk_live_...", "name": "my-outreach-demo", "created_at": "..." }
```

Save the key. It is only shown once.

Alternatively, generate a key from the dashboard at https://agentsentinelai.com/dashboard (Settings tab → API Keys).

---

## Step 2 — Download the SDK

The SDK is a single Python file. No pip install needed.

```bash
curl -O https://raw.githubusercontent.com/SKhatter/sentinel-ai/main/sentinel_sdk.py
```

Or just use the `sentinel_sdk.py` already in this repository.

---

## Step 3 — Run the main pipeline

```bash
python pipeline.py --api-key sk_live_YOUR_KEY_HERE
```

To run against a local Sentinel server (for development):
```bash
python pipeline.py --api-key sk_live_YOUR_KEY_HERE --endpoint http://localhost:3001
```

**What happens:**

1. Contracts are registered for `personalize-agent` and `deliver-agent`
2. Research Agent scores 5 companies and writes the best lead to shared state
3. Sentinel validates the lead payload → Personalize Agent receives it
4. Personalize Agent generates a personalised email draft
5. Sentinel validates the email payload → Deliver Agent receives it
6. Deliver Agent sends the email and records the outcome

**Expected output:**
```
Registering agent contracts with Sentinel...
  ✓ personalize-agent contract registered
  ✓ deliver-agent contract registered

Starting pipeline  run_id=demo_a3f9c12b8d1e
Researching 5 companies...

Research done in 412ms
  Best lead : DataVault Inc  score=0.94

Handing off lead to personalize-agent...
  ✓ Handoff accepted

Personalization done in 187ms
  Subject : Quick question for DataVault Inc
  Confidence : 0.91

Handing off email draft to deliver-agent...
  ✓ Handoff accepted

============================================================
  EMAIL DELIVERED  |  DELIVERED
============================================================
  Company : DataVault Inc
  Subject : Quick question for DataVault Inc
  Msg ID  : msg_47291
  Status  : delivered
============================================================

Pipeline complete in 623ms
  run_id  : demo_a3f9c12b8d1e
  View at : https://agentsentinelai.com/dashboard
```

---

## Step 4 — Open the dashboard

Go to **https://agentsentinelai.com/dashboard**

Enter your API key in the Settings tab to enable authenticated views.

### Traces tab
Shows your `demo_...` run with each step's duration, status, and input/output payloads. Click any run to see the full step breakdown.

### Contracts tab
Shows the `personalize-agent` and `deliver-agent` contracts you registered, plus the handoff audit log (all accepted/rejected handoffs).

### State tab
Shows the `lead_research` key in the `demo_...` namespace. Each agent's writes are versioned — you can see all contributions without any data loss.

### Incidents tab
Auto-created incidents from any failed steps or rejected handoffs.

---

## Step 5 — See a contract violation

Run the bad handoff demo. Research Agent intentionally sends a broken payload — missing required fields, score out of range, invalid tier.

```bash
python demo_bad_handoff.py --api-key sk_live_YOUR_KEY_HERE
```

**Expected output:**
```
run_id: demo_bad_a3c9f2d1
Attempting handoff with bad payload...

Payload sent:
  lead_id: acme_001
  score: 1.5
  tier: vip
  (company: MISSING)
  (industry: MISSING)

✓ Handoff BLOCKED by Sentinel
  from : research-agent
  to   : personalize-agent
  Violations:
    • "company" is required
    • "industry" is required
    • "score" must be <= 1
    • "tier" must be one of: free, pro, enterprise

  The Personalize Agent never ran.
  An incident has been auto-created in the dashboard.
```

Check the **Incidents** tab and the **Contracts** tab's handoff audit log to see the rejected handoff.

---

## Step 6 — See atomic state coordination

Run the concurrent write demo. Two agents race to update the same state key at the same time.

```bash
python demo_state_conflict.py --api-key sk_live_YOUR_KEY_HERE
```

**Expected output:**
```
run_id: demo_conflict_b2a1f9e4
Launching agent-a and agent-b concurrently...

  [agent-a] wrote score=0.87  → version 1
  [agent-b] wrote tone=positive → version 2

✓ Both agents completed successfully
  Final state version : 2
  Final state keys    : ['research', 'sentiment']

  Without Sentinel: one agent's write would have been silently lost.
  With Sentinel:    both writes are safely merged via compare-and-swap.
```

Open the **State** tab in the dashboard — the key shows version 2, containing both agents' data.

---

## File layout

```
sentinel-ai-demo/
├── sentinel_sdk.py          # Sentinel Python SDK (single file, no install)
├── pipeline.py              # Main 3-agent pipeline
├── demo_bad_handoff.py      # Demo: contract violation blocks bad payload
├── demo_state_conflict.py   # Demo: concurrent agents, atomic state merge
├── agents/
│   ├── research_agent.py    # Agent 1: scores leads, writes to state
│   ├── personalize_agent.py # Agent 2: generates email, reads from state
│   └── deliver_agent.py     # Agent 3: delivers email, records outcome
└── README.md
```

---

## SDK quick-reference

### Initialize
```python
import sentinel
sentinel.init(api_key="sk_live_...", endpoint="https://agentsentinelai.com")
```

### Trace a workflow
```python
with sentinel.workflow("My Pipeline") as run:
    with run.step("agent-name", step_type="llm_call") as step:
        step.set_input({"query": "..."})
        result = my_agent.run(query)
        step.set_output({"result": result})
```

### Shared state (atomic)
```python
# Read
value, version = sentinel.get_state("run_id", "key")

# Write with conflict protection
new_version = sentinel.propose_state("run_id", "key", new_value, base_version=version)

# Auto-retry on conflict
sentinel.propose_state_with_retry("run_id", "key", lambda cur: {**cur, "new_field": "val"})
```

### Register agent contract
```python
sentinel.register_contract(
    agent="my-agent",
    accepts={
        "lead_id": {"type": "string", "required": True},
        "score":   {"type": "number", "min": 0, "max": 1},
    }
)
```

### Execute a validated handoff
```python
try:
    sentinel.handoff(
        from_agent="agent-a",
        to_agent="agent-b",
        run_id=run.run_id,
        payload=result,
    )
except sentinel.ContractViolationError as e:
    print(f"Blocked: {e.violations}")
    # Fix the payload and retry
```

---

## Full API reference

See the complete API manual at **https://agentsentinelai.com** (click "View API Manual").

---

*Sentinel.AI — The Control Plane for AI Agents*
*https://agentsentinelai.com*
