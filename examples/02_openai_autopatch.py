#!/usr/bin/env python3
"""
Integration Pattern 2: OpenAI Auto-Patch
==========================================
Call sentinel.patch_openai(client) ONCE at startup.
Every client.chat.completions.create() call is auto-traced from that point.
Your agent code is completely unchanged.

Best for: teams already using the OpenAI Python SDK.

Real usage (with actual OpenAI key):
    pip install openai
    python examples/02_openai_autopatch.py --api-key sk_live_... --openai-key sk-...

Simulated usage (no OpenAI key needed):
    python examples/02_openai_autopatch.py --api-key sk_live_... --simulate
"""

import argparse
import time
import random
import uuid
import sentinel


# ── Simulated OpenAI client (used when --simulate flag is set) ────────────────
class _MockChoice:
    def __init__(self, text):
        self.finish_reason = "stop"
        self.message = type("M", (), {"content": text, "role": "assistant"})()

class _MockUsage:
    def __init__(self):
        self.prompt_tokens = random.randint(100, 500)
        self.completion_tokens = random.randint(50, 200)
        self.total_tokens = self.prompt_tokens + self.completion_tokens

class _MockCompletions:
    def create(self, model="gpt-4o", messages=None, **kwargs):
        time.sleep(random.uniform(0.05, 0.2))
        last_msg = (messages or [{}])[-1].get("content", "")
        response_text = f"[Simulated {model} response to: {last_msg[:50]}...]"
        result = type("R", (), {
            "choices": [_MockChoice(response_text)],
            "usage": _MockUsage(),
            "model": model
        })()
        return result

class _MockChat:
    completions = _MockCompletions()

class SimulatedOpenAIClient:
    chat = _MockChat()


# ── Your existing agent code — ZERO CHANGES needed after patching ─────────────

def research_agent(client, query: str) -> str:
    """Existing agent — calls OpenAI directly. No sentinel imports here."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a lead research agent."},
            {"role": "user",   "content": f"Research companies for: {query}"}
        ]
    )
    return response.choices[0].message.content


def personalize_agent(client, research: str, company: str) -> str:
    """Existing agent — calls OpenAI directly. No sentinel imports here."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You write personalised outreach emails."},
            {"role": "user",   "content": f"Write an email for {company} based on: {research}"}
        ]
    )
    return response.choices[0].message.content


def qualify_agent(client, email: str) -> str:
    """Existing agent — calls OpenAI directly. No sentinel imports here."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You qualify outreach emails for quality."},
            {"role": "user",   "content": f"Score this email 1-10: {email[:200]}"}
        ]
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key",    required=True, help="Sentinel API key")
    parser.add_argument("--openai-key", default=None,  help="OpenAI API key (optional)")
    parser.add_argument("--endpoint",   default="https://www.agentsentinelai.com")
    parser.add_argument("--simulate",   action="store_true", help="Use simulated OpenAI (no real key needed)")
    args = parser.parse_args()

    # ── 1. Init Sentinel ──────────────────────────────────────────────────────
    sentinel.init(api_key=args.api_key, endpoint=args.endpoint)

    # ── 2. Create your OpenAI client (unchanged) ──────────────────────────────
    if args.simulate or not args.openai_key:
        print("Using simulated OpenAI client (pass --openai-key to use real OpenAI)\n")
        client = SimulatedOpenAIClient()
    else:
        import openai
        client = openai.OpenAI(api_key=args.openai_key)

    # ── 3. Patch the client — ONE LINE, then forget about it ─────────────────
    sentinel.patch_openai(client, workflow_name="OpenAI Lead Pipeline")
    print("OpenAI client patched. All calls are now auto-traced.\n")

    # ── 4. Set a shared run ID so all 3 agents appear in the same run ─────────
    run_id = f"openai_demo_{uuid.uuid4().hex[:10]}"
    sentinel.set_active_run(run_id=run_id, workflow_name="OpenAI Lead Pipeline")

    # ── 5. Your existing pipeline code — completely unchanged ─────────────────
    print("Step 1: Research...")
    research = research_agent(client, "find Series B fintech startups")
    print(f"  → {research[:80]}...")

    print("Step 2: Personalize...")
    email = personalize_agent(client, research, "Acme Corp")
    print(f"  → {email[:80]}...")

    print("Step 3: Qualify...")
    score = qualify_agent(client, email)
    print(f"  → {score[:80]}...")

    print(f"\nAll 3 OpenAI calls auto-traced as steps in run: {run_id}")
    print(f"View at: {args.endpoint}/dashboard → Traces tab")
