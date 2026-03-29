"""
Personalize Agent
=================
Simulates an LLM agent that writes a personalised outreach email.

Responsibilities:
  - Receive a validated lead payload via Sentinel handoff
  - Read additional context from Sentinel shared state
  - Generate a personalised email draft
  - Hand off the draft to the Deliver Agent
"""

import time
import random

import sentinel


# Simulated email templates — in a real agent this calls a model API
_TEMPLATES = [
    "Hi {name},\n\nI noticed {company} recently raised {funding} funding — congrats! "
    "We work with a lot of {industry} companies at your stage and help them [VALUE PROP].\n\n"
    "Would a 20-minute call make sense this week?\n\nBest,\nAlex",

    "Hey {name},\n\nYour work at {company} in the {industry} space caught my eye. "
    "Given your team size ({employees} people), I think [PRODUCT] could save you real time on [PAIN POINT].\n\n"
    "Open to a quick chat?\n\nThanks,\nAlex",

    "{name},\n\nI help {industry} companies like {company} with [CATEGORY]. "
    "Based on your {funding} stage, now might be the right time.\n\n"
    "Happy to share a few ideas — any interest?\n\nAlex",
]


def _generate_email(lead: dict) -> dict:
    """Fake LLM call: fills a template with lead data."""
    time.sleep(random.uniform(0.05, 0.2))
    template = random.choice(_TEMPLATES)
    draft = template.format(
        name=lead["company"].split()[0],  # first word as contact name
        company=lead["company"],
        industry=lead["industry"],
        funding=lead.get("funding", "recent"),
        employees=lead.get("employees", "your"),
    )
    confidence = round(random.uniform(0.7, 0.98), 2)
    return {
        "email_draft": draft,
        "confidence": confidence,
        "subject": f"Quick question for {lead['company']}",
        "to_company": lead["company"],
    }


def run(run_id: str, lead: dict) -> dict:
    """
    Generate a personalised email for the given lead.

    Reads supplementary context from Sentinel shared state, generates the draft,
    writes the result back to state, and returns the email payload for handoff.
    """
    with sentinel.workflow("Customer Outreach Pipeline", run_id=run_id) as run_ctx:

        # Read full research context from state (written by research-agent)
        with run_ctx.step("read-context", step_type="tool_call") as step:
            step.set_input({"namespace": run_id, "key": "lead_research"})
            context, version = sentinel.get_state(run_id, "lead_research")
            step.set_output({"version": version, "has_context": context is not None})

        # Generate personalised email
        with run_ctx.step("personalize-agent", step_type="llm_call") as step:
            step.set_input({
                "lead_id": lead["lead_id"],
                "company": lead["company"],
                "score":   lead["score"],
            })
            result = _generate_email(lead)
            step.set_output({"confidence": result["confidence"], "subject": result["subject"]})

        # Update state with the email draft
        with run_ctx.step("write-draft-state", step_type="tool_call") as step:
            step.set_input({"lead_id": lead["lead_id"]})

            def update_draft(current):
                current = current or {}
                current["email_draft"] = result
                current["personalized_by"] = "personalize-agent"
                return current

            sentinel.propose_state_with_retry(
                run_id, "lead_research",
                update_draft,
                agent_name="personalize-agent"
            )
            step.set_output({"draft_written": True})

    return result
