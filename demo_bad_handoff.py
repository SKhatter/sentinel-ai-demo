#!/usr/bin/env python3
"""
Demo: Contract Violation
========================
Shows what happens when Research Agent passes a bad payload to Personalize Agent.

Missing required fields + score out of range → Sentinel blocks the handoff,
raises ContractViolationError, and auto-creates an incident.

The Personalize Agent never runs with the bad data.

Usage:
    python demo_bad_handoff.py --api-key sk_live_...
"""

import argparse
import uuid
import sentinel


def run(api_key: str, endpoint: str):
    sentinel.init(api_key=api_key, endpoint=endpoint)

    # Re-register contracts (idempotent)
    sentinel.register_contract(
        agent="personalize-agent",
        accepts={
            "lead_id":   {"type": "string", "required": True},
            "company":   {"type": "string", "required": True},
            "score":     {"type": "number", "min": 0, "max": 1},
            "tier":      {"type": "string", "enum": ["free", "pro", "enterprise"]},
            "industry":  {"type": "string", "required": True},
        },
    )

    run_id = f"demo_bad_{uuid.uuid4().hex[:8]}"

    # Intentionally bad payload:
    #   - missing "company" (required)
    #   - missing "industry" (required)
    #   - score = 1.5 (exceeds max of 1)
    #   - tier = "vip" (not in enum)
    bad_payload = {
        "lead_id": "acme_001",
        # "company" intentionally omitted
        # "industry" intentionally omitted
        "score": 1.5,       # must be <= 1
        "tier": "vip",      # must be free|pro|enterprise
    }

    print(f"\nrun_id: {run_id}")
    print("Attempting handoff with bad payload...\n")
    print("Payload sent:")
    for k, v in bad_payload.items():
        print(f"  {k}: {v}")
    print("  (company: MISSING)")
    print("  (industry: MISSING)")

    try:
        sentinel.handoff(
            from_agent="research-agent",
            to_agent="personalize-agent",
            run_id=run_id,
            payload=bad_payload,
        )
        print("\n[unexpected] Handoff accepted — this should not happen!")

    except sentinel.ContractViolationError as e:
        print(f"\n✓ Handoff BLOCKED by Sentinel")
        print(f"  from : research-agent")
        print(f"  to   : personalize-agent")
        print(f"  Violations:")
        for v in e.violations:
            print(f"    • {v}")
        print(f"\n  The Personalize Agent never ran.")
        print(f"  An incident has been auto-created in the dashboard.")
        print(f"\n  View at: {endpoint}/dashboard  → Incidents tab")
        print(f"  run_id : {run_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo: bad handoff blocked by Sentinel")
    parser.add_argument("--api-key",  required=True)
    parser.add_argument("--endpoint", default="https://www.agentsentinelai.com")
    args = parser.parse_args()
    run(args.api_key, args.endpoint)
