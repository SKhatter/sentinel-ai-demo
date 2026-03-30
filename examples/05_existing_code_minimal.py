#!/usr/bin/env python3
"""
Integration Pattern 5: Wrapping Existing Code — Absolute Minimum Changes
==========================================================================
You have a working multi-agent pipeline. You want Sentinel tracing with
the fewest possible changes to your code.

This shows 3 levels of effort:
  Level A — wrap the entire pipeline in one `with sentinel.workflow()` block (5 lines added)
  Level B — also wrap individual agents for per-step visibility (3 lines per agent)
  Level C — use patch_openai/patch_anthropic so even Level B isn't needed

Best for: teams who want to start immediately and add detail later.

Usage:
    python examples/05_existing_code_minimal.py --api-key sk_live_...
"""

import argparse
import time
import random
import uuid
import sentinel


# ════════════════════════════════════════════════════════════════
# YOUR ORIGINAL CODE — completely unchanged below this line
# ════════════════════════════════════════════════════════════════

def agent_a_research(query: str) -> dict:
    time.sleep(random.uniform(0.05, 0.15))
    return {"leads": ["Acme Corp", "NovaTech", "BlueSky"], "query": query}

def agent_b_score(leads: list) -> list:
    time.sleep(random.uniform(0.03, 0.1))
    return [{"name": l, "score": round(random.uniform(0.5, 0.99), 2)} for l in leads]

def agent_c_email(lead: dict) -> str:
    time.sleep(random.uniform(0.05, 0.2))
    return f"Hi {lead['name']}, your score is {lead['score']}. Let's connect!"

def agent_d_send(email: str, lead: dict) -> dict:
    time.sleep(random.uniform(0.02, 0.08))
    return {"status": "sent", "to": lead["name"], "msg_id": f"msg_{random.randint(1000,9999)}"}


# ════════════════════════════════════════════════════════════════
# LEVEL A — minimum viable: one workflow wrapper (5 lines total)
# Gives you: run tracking, failure detection, total duration
# ════════════════════════════════════════════════════════════════

def run_level_a(run_id: str):
    print("\n── Level A: one workflow wrapper ──")

    # ADD: wrap everything in sentinel.workflow()
    with sentinel.workflow("Outreach Pipeline", run_id=run_id) as run:
        # Your existing code — completely unchanged
        research = agent_a_research("fintech leads")
        scored   = agent_b_score(research["leads"])
        best     = max(scored, key=lambda x: x["score"])
        email    = agent_c_email(best)
        result   = agent_d_send(email, best)

    print(f"  Sent to {result['to']} — msg_id={result['msg_id']}")
    print(f"  Dashboard: shows 1 run, status, total duration")
    print(f"  Missing:   no per-agent steps (can't see where time was spent)")


# ════════════════════════════════════════════════════════════════
# LEVEL B — per-agent steps (3 lines per agent added)
# Gives you: A→B→C→D flow, latency per agent, input/output payloads
# ════════════════════════════════════════════════════════════════

def run_level_b(run_id: str):
    print("\n── Level B: per-agent steps ──")

    with sentinel.workflow("Outreach Pipeline", run_id=run_id) as run:

        # ADD: wrap each agent call in run.step()
        with run.step("agent-a-research", step_type="llm_call") as step:
            step.set_input({"query": "fintech leads"})
            research = agent_a_research("fintech leads")
            step.set_output({"leads_found": len(research["leads"])})

        with run.step("agent-b-score", step_type="llm_call") as step:
            step.set_input({"leads": research["leads"]})
            scored = agent_b_score(research["leads"])
            best   = max(scored, key=lambda x: x["score"])
            step.set_output({"best": best["name"], "score": best["score"]})

        with run.step("agent-c-email", step_type="llm_call") as step:
            step.set_input({"lead": best})
            email = agent_c_email(best)
            step.set_output({"email_length": len(email)})

        with run.step("agent-d-send", step_type="notification") as step:
            step.set_input({"to": best["name"]})
            result = agent_d_send(email, best)
            step.set_output(result)

    print(f"  Sent to {result['to']}")
    print(f"  Dashboard: shows A→B→C→D DAG, latency per step, input/output")


# ════════════════════════════════════════════════════════════════
# LEVEL C — auto-patch (zero per-agent changes after patching)
# Same visibility as Level B but no code changes inside functions
# ════════════════════════════════════════════════════════════════

def run_level_c(run_id: str):
    print("\n── Level C: decorator on each function (zero changes inside) ──")

    # Patch existing functions with decorator at the call site
    # (or add @trace_step to the function definition for permanent tracing)
    traced_research = sentinel.trace_step(name="agent-a-research", step_type="llm_call",
                                          workflow_name="Outreach Pipeline", run_id=run_id)(agent_a_research)
    traced_score    = sentinel.trace_step(name="agent-b-score",    step_type="llm_call",
                                          workflow_name="Outreach Pipeline", run_id=run_id)(agent_b_score)
    traced_email    = sentinel.trace_step(name="agent-c-email",    step_type="llm_call",
                                          workflow_name="Outreach Pipeline", run_id=run_id)(agent_c_email)
    traced_send     = sentinel.trace_step(name="agent-d-send",     step_type="notification",
                                          workflow_name="Outreach Pipeline", run_id=run_id)(agent_d_send)

    # Call traced versions — originals are untouched
    research = traced_research("fintech leads")
    scored   = traced_score(research["leads"])
    best     = max(scored, key=lambda x: x["score"])
    email    = traced_email(best)
    result   = traced_send(email, best)

    print(f"  Sent to {result['to']}")
    print(f"  Dashboard: same as Level B — no changes inside agent functions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key",  required=True)
    parser.add_argument("--endpoint", default="https://www.agentsentinelai.com")
    parser.add_argument("--level",    choices=["a", "b", "c", "all"], default="all")
    args = parser.parse_args()

    sentinel.init(api_key=args.api_key, endpoint=args.endpoint)

    levels = ["a", "b", "c"] if args.level == "all" else [args.level]

    for level in levels:
        run_id = f"level_{level}_{uuid.uuid4().hex[:8]}"
        print(f"\nrun_id: {run_id}")
        if level == "a": run_level_a(run_id)
        if level == "b": run_level_b(run_id)
        if level == "c": run_level_c(run_id)

    print(f"\nView all runs at: {args.endpoint}/dashboard → Workflows tab")
