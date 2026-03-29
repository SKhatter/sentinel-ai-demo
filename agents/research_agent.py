"""
Research Agent
==============
Simulates an LLM agent that discovers and scores leads.
In a real system this would call OpenAI / Anthropic / a web scraper.

Responsibilities:
  - Accept a list of company names
  - Score each lead (0.0 – 1.0) based on simulated research
  - Write the enriched lead profile into Sentinel shared state
  - Hand off the best lead to the Personalize Agent
"""

import time
import random

import sentinel


# Simulated "LLM" research — in a real agent this calls a model API
_COMPANY_DATA = {
    "Acme Corp":        {"industry": "fintech",    "employees": 500,  "funding": "Series B"},
    "NovaTech":         {"industry": "healthcare", "employees": 120,  "funding": "Series A"},
    "Quantum Dynamics": {"industry": "defense",    "employees": 2000, "funding": "Public"},
    "BlueSky Labs":     {"industry": "SaaS",       "employees": 45,   "funding": "Seed"},
    "DataVault Inc":    {"industry": "data",       "employees": 310,  "funding": "Series C"},
}


def _simulate_research(company: str) -> dict:
    """Fake LLM call: returns enriched company data with a score."""
    time.sleep(random.uniform(0.05, 0.15))  # simulate API latency
    data = _COMPANY_DATA.get(company, {"industry": "unknown", "employees": 50, "funding": "Unknown"})
    score = round(random.uniform(0.5, 0.99), 2)
    return {
        "lead_id":   company.lower().replace(" ", "_"),
        "company":   company,
        "industry":  data["industry"],
        "employees": data["employees"],
        "funding":   data["funding"],
        "score":     score,
        "tier":      "enterprise" if data["employees"] > 200 else ("pro" if data["employees"] > 50 else "free"),
    }


def run(run_id: str, companies: list) -> dict:
    """
    Research a list of companies and return the highest-scored lead.

    Records each company as a sub-step, writes the full results to Sentinel
    atomic state, and returns the best lead for handoff.
    """
    results = []

    with sentinel.workflow("Customer Outreach Pipeline", run_id=run_id) as run_ctx:
        for company in companies:
            with run_ctx.step(f"research:{company}", step_type="llm_call") as step:
                step.set_input({"company": company})
                lead = _simulate_research(company)
                step.set_output(lead)
                results.append(lead)

        # Sort by score — best lead goes first
        results.sort(key=lambda x: x["score"], reverse=True)
        best = results[0]

        # Write ALL results to shared state so other agents can read them
        with run_ctx.step("write-state", step_type="tool_call") as step:
            step.set_input({"leads_count": len(results)})

            def update_leads(current):
                current = current or {}
                current["all_leads"] = results
                current["best_lead"] = best
                current["researched_by"] = "research-agent"
                return current

            sentinel.propose_state_with_retry(
                run_id, "lead_research",
                update_leads,
                agent_name="research-agent"
            )
            step.set_output({"best_lead": best["company"], "score": best["score"]})

    return best
