#!/usr/bin/env python3
"""
Integration Pattern 3: Anthropic Auto-Patch
=============================================
Same idea as 02_openai_autopatch.py but for Anthropic's SDK.
One call to sentinel.patch_anthropic(client) — everything else is unchanged.

Best for: teams using Claude (claude-opus-4-6, claude-sonnet-4-6, etc.)

Real usage:
    pip install anthropic
    python examples/03_anthropic_autopatch.py --api-key sk_live_... --anthropic-key sk-ant-...

Simulated usage:
    python examples/03_anthropic_autopatch.py --api-key sk_live_... --simulate
"""

import argparse
import time
import random
import uuid
import sentinel


# ── Simulated Anthropic client ────────────────────────────────────────────────
class _MockAnthropicUsage:
    def __init__(self):
        self.input_tokens  = random.randint(100, 800)
        self.output_tokens = random.randint(50, 300)

class _MockContent:
    def __init__(self, text):
        self.type = "text"
        self.text = text

class SimulatedAnthropicClient:
    class messages:
        @staticmethod
        def create(model="claude-opus-4-6", messages=None, max_tokens=1024, **kwargs):
            time.sleep(random.uniform(0.05, 0.2))
            last_msg = (messages or [{}])[-1].get("content", "")
            text = f"[Simulated {model} response to: {last_msg[:60]}...]"
            result = type("R", (), {
                "content": [_MockContent(text)],
                "usage": _MockAnthropicUsage(),
                "stop_reason": "end_turn",
                "model": model
            })()
            return result


# ── Your existing agent code — ZERO CHANGES needed after patching ─────────────

def intake_agent(client, task: str) -> str:
    """Intake agent — uses Claude. No sentinel imports."""
    resp = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=512,
        messages=[
            {"role": "user", "content": f"Parse this task and extract key entities: {task}"}
        ]
    )
    return resp.content[0].text


def research_agent(client, entities: str) -> str:
    """Research agent — uses Claude. No sentinel imports."""
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": f"Research these companies and score them: {entities}"}
        ]
    )
    return resp.content[0].text


def synthesis_agent(client, research: str) -> str:
    """Synthesis agent — uses Claude Haiku for speed. No sentinel imports."""
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[
            {"role": "user", "content": f"Summarise this research in 2 sentences: {research}"}
        ]
    )
    return resp.content[0].text


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key",       required=True)
    parser.add_argument("--anthropic-key", default=None)
    parser.add_argument("--endpoint",      default="https://www.agentsentinelai.com")
    parser.add_argument("--simulate",      action="store_true")
    args = parser.parse_args()

    sentinel.init(api_key=args.api_key, endpoint=args.endpoint)

    if args.simulate or not args.anthropic_key:
        print("Using simulated Anthropic client\n")
        client = SimulatedAnthropicClient()
    else:
        import anthropic
        client = anthropic.Anthropic(api_key=args.anthropic_key)

    # ONE LINE — patch the client
    sentinel.patch_anthropic(client, workflow_name="Claude Research Pipeline")
    print("Anthropic client patched. All calls are now auto-traced.\n")

    run_id = f"anthropic_demo_{uuid.uuid4().hex[:10]}"
    sentinel.set_active_run(run_id=run_id, workflow_name="Claude Research Pipeline")

    print("Step 1: Intake...")
    entities = intake_agent(client, "Research Series B fintech companies in NYC")
    print(f"  → {entities[:80]}...")

    print("Step 2: Research...")
    research = research_agent(client, entities)
    print(f"  → {research[:80]}...")

    print("Step 3: Synthesis...")
    summary = synthesis_agent(client, research)
    print(f"  → {summary[:80]}...")

    print(f"\nAll 3 Claude calls auto-traced in run: {run_id}")
    print(f"View at: {args.endpoint}/dashboard → Traces tab")
