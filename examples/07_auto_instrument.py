#!/usr/bin/env python3
"""
Integration Pattern 7: auto_instrument()
==========================================
One line replaces all manual patching. Sentinel auto-detects installed
LLM SDKs (openai, anthropic, langchain) and patches them automatically.

Usage:
    python examples/07_auto_instrument.py --api-key sk_live_...
    python examples/07_auto_instrument.py --api-key sk_live_... --endpoint http://localhost:3001
"""

import argparse
import time
import random
import uuid
import sys
import os

# ── Simulated OpenAI class (mirrors the real openai.resources structure) ───────
# auto_instrument() patches openai.resources.chat.completions.Completions.create
# at the class level — so we subclass it to get the patch automatically.

class _MockUsage:
    def __init__(self):
        self.prompt_tokens    = random.randint(100, 400)
        self.completion_tokens = random.randint(50, 200)
        self.total_tokens     = self.prompt_tokens + self.completion_tokens

class _MockChoice:
    def __init__(self, text):
        self.finish_reason = "stop"
        self.message = type("M", (), {"content": text, "role": "assistant"})()

def _make_mock_response(model, messages):
    last_msg = next((m["content"] for m in reversed(messages)
                     if m.get("role") == "user"), "")
    text = f"[Simulated {model} response to: {last_msg[:60]}]"
    return type("R", (), {
        "choices": [_MockChoice(text)],
        "usage":   _MockUsage(),
        "model":   model,
    })()


def _install_mock_openai():
    """
    Replace openai.resources.chat.completions.Completions.create with a mock
    BEFORE auto_instrument() is called, so the patch applies to our mock too.
    We do this by installing a fake openai module structure into sys.modules.
    """
    import types

    # Build a fake openai module tree that mirrors the real structure
    fake_openai = types.ModuleType("openai")
    fake_resources = types.ModuleType("openai.resources")
    fake_chat = types.ModuleType("openai.resources.chat")
    fake_completions_mod = types.ModuleType("openai.resources.chat.completions")

    class Completions:
        def create(self, model="gpt-4o", messages=None, **kwargs):
            time.sleep(random.uniform(0.05, 0.15))
            return _make_mock_response(model, messages or [])

    fake_completions_mod.Completions = Completions
    fake_chat.completions = fake_completions_mod
    fake_resources.chat = fake_chat
    fake_openai.resources = fake_resources

    sys.modules["openai"] = fake_openai
    sys.modules["openai.resources"] = fake_resources
    sys.modules["openai.resources.chat"] = fake_chat
    sys.modules["openai.resources.chat.completions"] = fake_completions_mod

    # Return a mock client that uses the Completions class so the patch applies
    class MockClient:
        class chat:
            completions = Completions()
    return MockClient()


# ── Your existing agent functions — no sentinel imports ────────────────────────

def research_agent(client, query: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a research agent."},
            {"role": "user",   "content": f"Research: {query}"}
        ]
    )
    return response.choices[0].message.content


def personalize_agent(client, research: str, company: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You write personalised outreach emails."},
            {"role": "user",   "content": f"Write email for {company} based on: {research}"}
        ]
    )
    return response.choices[0].message.content


def qualify_agent(client, email: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You qualify outreach emails."},
            {"role": "user",   "content": f"Score 1-10: {email[:200]}"}
        ]
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key",    required=True)
    parser.add_argument("--openai-key", default=None, help="Real OpenAI key (optional)")
    parser.add_argument("--endpoint",   default="https://www.agentsentinelai.com")
    args = parser.parse_args()

    print("=== auto_instrument() demo ===\n")

    # ── Step 1: Install mock openai if no real key provided ───────────────────
    if args.openai_key:
        import openai as _oai
        client = _oai.OpenAI(api_key=args.openai_key)
        print("Using real OpenAI client.\n")
    else:
        print("No --openai-key provided. Using simulated OpenAI.\n")
        client = _install_mock_openai()

    # ── Step 2: ONE LINE — auto-detect and patch everything ───────────────────
    import sentinel
    patched = sentinel.auto_instrument(
        api_key=args.api_key,
        workflow_name="Auto Instrument Demo",
        endpoint=args.endpoint,
    )
    print(f"SDKs patched: {patched}\n")

    # ── Step 3: Set a shared run ID so all steps appear in the same run ───────
    run_id = f"auto_{uuid.uuid4().hex[:10]}"
    sentinel.set_active_run(run_id=run_id, workflow_name="Auto Instrument Demo")

    # ── Step 4: Your existing pipeline — completely unchanged ─────────────────
    print("Running pipeline (all calls auto-traced)...\n")

    print("Step 1: Research...")
    research = research_agent(client, "find Series B fintech startups")
    print(f"  → {research[:80]}")

    print("Step 2: Personalize...")
    email = personalize_agent(client, research, "Acme Corp")
    print(f"  → {email[:80]}")

    print("Step 3: Qualify...")
    score = qualify_agent(client, email)
    print(f"  → {score[:80]}")

    print(f"\n✓ 3 steps auto-traced under run_id: {run_id}")
    print(f"View at: {args.endpoint}/dashboard → Traces tab")
