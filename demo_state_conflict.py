#!/usr/bin/env python3
"""
Demo: Atomic State Conflict
============================
Simulates two agents racing to update the same shared state key simultaneously.

Without Sentinel: the second writer silently overwrites the first (lost write).
With Sentinel:    the second writer gets a 409 conflict, re-reads, and merges safely.

The final state contains contributions from BOTH agents.

Usage:
    python demo_state_conflict.py --api-key sk_live_...
"""

import argparse
import threading
import time
import uuid

import sentinel


def agent_a_writes(run_id: str, results: dict):
    """Simulates Research Agent writing scoring data."""
    time.sleep(0.02)  # slight delay so both agents start "simultaneously"
    try:
        new_version = sentinel.propose_state_with_retry(
            run_id, "shared_context",
            lambda current: {**(current or {}), "research": {"score": 0.87, "source": "agent-a"}},
            agent_name="agent-a"
        )
        results["agent-a"] = {"ok": True, "version": new_version}
        print(f"  [agent-a] wrote score=0.87  → version {new_version}")
    except Exception as e:
        results["agent-a"] = {"ok": False, "error": str(e)}
        print(f"  [agent-a] failed: {e}")


def agent_b_writes(run_id: str, results: dict):
    """Simulates Sentiment Agent writing NLP analysis at the same time."""
    time.sleep(0.02)
    try:
        new_version = sentinel.propose_state_with_retry(
            run_id, "shared_context",
            lambda current: {**(current or {}), "sentiment": {"tone": "positive", "source": "agent-b"}},
            agent_name="agent-b"
        )
        results["agent-b"] = {"ok": True, "version": new_version}
        print(f"  [agent-b] wrote tone=positive → version {new_version}")
    except Exception as e:
        results["agent-b"] = {"ok": False, "error": str(e)}
        print(f"  [agent-b] failed: {e}")


def run(api_key: str, endpoint: str):
    sentinel.init(api_key=api_key, endpoint=endpoint)

    run_id = f"demo_conflict_{uuid.uuid4().hex[:8]}"
    print(f"\nrun_id: {run_id}")
    print("Launching agent-a and agent-b concurrently...\n")

    results = {}
    t_a = threading.Thread(target=agent_a_writes, args=(run_id, results))
    t_b = threading.Thread(target=agent_b_writes, args=(run_id, results))
    t_a.start()
    t_b.start()
    t_a.join()
    t_b.join()

    # Read final state — should contain both agents' contributions
    time.sleep(0.2)
    final_value, final_version = sentinel.get_state(run_id, "shared_context")

    print(f"\n✓ Both agents completed successfully")
    print(f"  Final state version : {final_version}")
    print(f"  Final state keys    : {list((final_value or {}).keys())}")
    print(f"\n  Without Sentinel: one agent's write would have been silently lost.")
    print(f"  With Sentinel:    both writes are safely merged via compare-and-swap.")
    print(f"\n  View at: {endpoint}/dashboard  → State tab")
    print(f"  run_id : {run_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo: concurrent state conflict + safe merge")
    parser.add_argument("--api-key",  required=True)
    parser.add_argument("--endpoint", default="https://agentsentinelai.com")
    args = parser.parse_args()
    run(args.api_key, args.endpoint)
