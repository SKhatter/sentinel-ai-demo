#!/usr/bin/env python3
"""
Customer Outreach Pipeline
==========================
Demonstrates a 3-agent workflow traced end-to-end through Sentinel.AI.

Agents:
  1. Research Agent    — scores a list of companies, writes best lead to shared state
  2. Personalize Agent — generates a personalised email, receives lead via handoff
  3. Deliver Agent     — sends the email, receives draft via handoff

Sentinel features demonstrated:
  ✓ Workflow + step tracing (live in dashboard → Traces tab)
  ✓ Atomic shared state   (live in dashboard → State tab)
  ✓ Agent contracts        (live in dashboard → Contracts tab)
  ✓ Handoff validation     (bad payloads blocked before reaching the next agent)
  ✓ Automatic incident on failure

Usage:
    python pipeline.py --api-key sk_live_...
    python pipeline.py --api-key sk_live_... --endpoint http://localhost:3001
"""

import argparse
import sys
import time

import sentinel
from agents import research_agent, personalize_agent, deliver_agent


# ── Contracts ─────────────────────────────────────────────────────────────────
# Register once at startup — Sentinel enforces these on every handoff.

def register_contracts():
    print("Registering agent contracts with Sentinel...")

    sentinel.register_contract(
        agent="personalize-agent",
        accepts={
            "lead_id":   {"type": "string",  "required": True},
            "company":   {"type": "string",  "required": True},
            "score":     {"type": "number",  "min": 0, "max": 1},
            "tier":      {"type": "string",  "enum": ["free", "pro", "enterprise"]},
            "industry":  {"type": "string",  "required": True},
            "employees": {"type": "number"},
            "funding":   {"type": "string"},
        },
        produces={
            "email_draft": {"type": "string", "max_length": 2000},
            "confidence":  {"type": "number", "min": 0, "max": 1},
            "subject":     {"type": "string"},
            "to_company":  {"type": "string"},
        },
        description="Generates personalised outreach emails from lead research data"
    )

    sentinel.register_contract(
        agent="deliver-agent",
        accepts={
            "email_draft": {"type": "string", "required": True, "max_length": 2000},
            "confidence":  {"type": "number", "min": 0, "max": 1},
            "subject":     {"type": "string", "required": True},
            "to_company":  {"type": "string", "required": True},
        },
        produces={
            "message_id": {"type": "string"},
            "status":     {"type": "string", "enum": ["delivered", "bounced"]},
            "provider":   {"type": "string"},
        },
        description="Delivers email drafts and records send status"
    )

    print("  ✓ personalize-agent contract registered")
    print("  ✓ deliver-agent contract registered\n")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(run_id: str):
    companies = [
        "Acme Corp",
        "NovaTech",
        "BlueSky Labs",
        "DataVault Inc",
        "Quantum Dynamics",
    ]

    print(f"Starting pipeline  run_id={run_id}")
    print(f"Researching {len(companies)} companies...\n")

    # Step 1 — Research
    t0 = time.time()
    best_lead = research_agent.run(run_id, companies)
    print(f"Research done in {int((time.time()-t0)*1000)}ms")
    print(f"  Best lead : {best_lead['company']}  score={best_lead['score']}\n")

    # Step 2 — Handoff: Research → Personalize
    # Sentinel validates the payload against personalize-agent's contract before delivery.
    print("Handing off lead to personalize-agent...")
    try:
        sentinel.handoff(
            from_agent="research-agent",
            to_agent="personalize-agent",
            run_id=run_id,
            payload=best_lead,
        )
        print("  ✓ Handoff accepted\n")
    except sentinel.ContractViolationError as e:
        print(f"  ✗ Handoff rejected: {e.violations}")
        sys.exit(1)

    # Step 3 — Personalize
    t1 = time.time()
    email = personalize_agent.run(run_id, best_lead)
    print(f"Personalization done in {int((time.time()-t1)*1000)}ms")
    print(f"  Subject : {email['subject']}")
    print(f"  Confidence : {email['confidence']}\n")

    # Step 4 — Handoff: Personalize → Deliver
    print("Handing off email draft to deliver-agent...")
    try:
        sentinel.handoff(
            from_agent="personalize-agent",
            to_agent="deliver-agent",
            run_id=run_id,
            payload=email,
        )
        print("  ✓ Handoff accepted\n")
    except sentinel.ContractViolationError as e:
        print(f"  ✗ Handoff rejected: {e.violations}")
        sys.exit(1)

    # Step 5 — Deliver
    result = deliver_agent.run(run_id, email)

    total_ms = int((time.time() - t0) * 1000)
    print(f"Pipeline complete in {total_ms}ms")
    print(f"  run_id  : {run_id}")
    print(f"  View at : https://agentsentinelai.com/dashboard\n")

    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentinel.AI demo pipeline")
    parser.add_argument("--api-key",  required=True,  help="Your Sentinel API key (sk_live_...)")
    parser.add_argument("--endpoint", default="https://agentsentinelai.com",
                        help="Sentinel endpoint (default: https://agentsentinelai.com)")
    parser.add_argument("--run-id",   default=None,    help="Optional stable run ID")
    args = parser.parse_args()

    sentinel.init(api_key=args.api_key, endpoint=args.endpoint)
    register_contracts()

    import uuid
    run_id = args.run_id or f"demo_{uuid.uuid4().hex[:12]}"
    run_pipeline(run_id)
