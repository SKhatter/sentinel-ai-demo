#!/usr/bin/env python3
"""
Integration Pattern 1: Decorator
=================================
The @sentinel.trace_step decorator wraps any existing function.
ONE line change per agent function — the function body is untouched.

Best for: teams with standalone agent functions they don't want to refactor.

Usage:
    python examples/01_decorator.py --api-key sk_live_...
"""

import argparse
import time
import random
import sentinel

# ── Existing agent functions (pretend these already exist in your codebase) ──

# BEFORE (original code):
# def research_agent(query: str) -> dict: ...
# def scoring_agent(leads: list) -> list: ...
# def email_agent(lead: dict) -> str: ...

# AFTER: just add the decorator — nothing else changes

@sentinel.trace_step(name="research-agent", step_type="llm_call", workflow_name="Lead Pipeline")
def research_agent(query: str) -> dict:
    """Simulates an LLM that finds company leads."""
    time.sleep(random.uniform(0.05, 0.15))
    return {
        "leads": [
            {"company": "Acme Corp",   "industry": "fintech"},
            {"company": "NovaTech",    "industry": "healthcare"},
            {"company": "BlueSky Labs", "industry": "SaaS"},
        ],
        "query": query
    }


@sentinel.trace_step(name="scoring-agent", step_type="llm_call", workflow_name="Lead Pipeline")
def scoring_agent(leads: list) -> list:
    """Simulates an LLM that scores each lead 0–1."""
    time.sleep(random.uniform(0.05, 0.1))
    return [{"score": round(random.uniform(0.5, 0.99), 2), **lead} for lead in leads]


@sentinel.trace_step(name="email-agent", step_type="llm_call", workflow_name="Lead Pipeline")
def email_agent(lead: dict) -> str:
    """Simulates an LLM that writes a personalised email."""
    time.sleep(random.uniform(0.05, 0.15))
    return f"Hi {lead['company']}, I noticed your work in {lead['industry']}..."


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--endpoint", default="https://www.agentsentinelai.com")
    args = parser.parse_args()

    sentinel.init(api_key=args.api_key, endpoint=args.endpoint)

    print("Running Lead Pipeline with @trace_step decorators...\n")

    leads   = research_agent("find fintech and healthcare leads")
    scored  = scoring_agent(leads["leads"])
    best    = max(scored, key=lambda x: x["score"])
    email   = email_agent(best)

    print(f"Best lead : {best['company']}  score={best['score']}")
    print(f"Email     : {email[:60]}...")
    print(f"\nView at   : {args.endpoint}/dashboard → Traces tab")
