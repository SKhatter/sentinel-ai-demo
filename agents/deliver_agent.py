"""
Deliver Agent
=============
Simulates the final delivery step: logging/sending the email.

Responsibilities:
  - Receive the validated email payload via Sentinel handoff
  - "Send" the email (simulated — prints to stdout)
  - Record the delivery result in Sentinel state
  - Mark the workflow as complete
"""

import time
import random

import sentinel


def _simulate_send(email_draft: str, subject: str, company: str) -> dict:
    """Fake email send — in production this calls SendGrid / Resend / SES."""
    time.sleep(random.uniform(0.02, 0.08))
    # 95% success rate to make the demo interesting
    success = random.random() > 0.05
    return {
        "message_id": f"msg_{random.randint(10000, 99999)}",
        "status": "delivered" if success else "bounced",
        "provider": "mock-smtp",
        "company": company,
        "subject": subject,
    }


def run(run_id: str, email: dict) -> dict:
    """
    Deliver the email and record the result.

    Reads from Sentinel state, attempts delivery, writes outcome back.
    """
    with sentinel.workflow("Customer Outreach Pipeline", run_id=run_id) as run_ctx:

        # Deliver the email
        with run_ctx.step("deliver-agent", step_type="notification") as step:
            step.set_input({
                "to_company": email.get("to_company"),
                "subject":    email.get("subject"),
            })
            result = _simulate_send(
                email["email_draft"],
                email.get("subject", "(no subject)"),
                email.get("to_company", "unknown"),
            )
            step.set_output(result)

            print(f"\n{'='*60}")
            print(f"  EMAIL DELIVERED  |  {result['status'].upper()}")
            print(f"{'='*60}")
            print(f"  Company : {email.get('to_company')}")
            print(f"  Subject : {email.get('subject')}")
            print(f"  Msg ID  : {result['message_id']}")
            print(f"  Status  : {result['status']}")
            print(f"{'='*60}\n")

        # Write delivery result to shared state
        with run_ctx.step("record-delivery", step_type="tool_call") as step:
            step.set_input({"message_id": result["message_id"]})

            def update_delivery(current):
                current = current or {}
                current["delivery"] = result
                current["delivered_by"] = "deliver-agent"
                return current

            sentinel.propose_state_with_retry(
                run_id, "lead_research",
                update_delivery,
                agent_name="deliver-agent"
            )
            step.set_output({"recorded": True})

    return result
