#!/usr/bin/env python3
"""
Integration Pattern 4: LangChain Callback Handler
===================================================
Pass sentinel.LangChainCallback() to any LangChain LLM, chain, or agent.
Every LLM call, chain step, and tool use is auto-traced — zero changes to
your chain logic.

Best for: teams using LangChain / LangGraph.

Real usage:
    pip install langchain langchain-openai
    python examples/04_langchain_callback.py --api-key sk_live_... --openai-key sk-...

Simulated usage (no LangChain installed):
    python examples/04_langchain_callback.py --api-key sk_live_... --simulate
"""

import argparse
import time
import random
import uuid
import sentinel


# ── Simulated LangChain environment (when --simulate is used) ─────────────────
class SimulatedLLM:
    """Mimics a LangChain ChatOpenAI object."""

    def __init__(self, model="gpt-4o", callbacks=None):
        self.model = model
        self.callbacks = callbacks or []

    def invoke(self, prompt: str) -> str:
        # Fire LangChain-style callbacks
        fake_run_id = uuid.uuid4()
        serialized = {"id": ["langchain", "chat_models", self.model]}

        for cb in self.callbacks:
            if hasattr(cb, "on_llm_start"):
                cb.on_llm_start(serialized, [prompt], run_id=fake_run_id)

        time.sleep(random.uniform(0.05, 0.2))
        text = f"[{self.model}] Response to: {prompt[:60]}..."

        class FakeGen:
            def __init__(self, t): self.text = t
        class FakeResp:
            def __init__(self, t): self.generations = [[FakeGen(t)]]; self.llm_output = {"token_usage": {"total_tokens": random.randint(100, 500)}}

        for cb in self.callbacks:
            if hasattr(cb, "on_llm_end"):
                cb.on_llm_end(FakeResp(text), run_id=fake_run_id)

        return text


class SimulatedTool:
    """Mimics a LangChain Tool."""

    def __init__(self, name: str, callbacks=None):
        self.name = name
        self.callbacks = callbacks or []

    def run(self, input_str: str) -> str:
        fake_run_id = uuid.uuid4()
        for cb in self.callbacks:
            if hasattr(cb, "on_tool_start"):
                cb.on_tool_start({"name": self.name}, input_str, run_id=fake_run_id)

        time.sleep(random.uniform(0.02, 0.1))
        output = f"[{self.name}] result for: {input_str[:40]}..."

        for cb in self.callbacks:
            if hasattr(cb, "on_tool_end"):
                cb.on_tool_end(output, run_id=fake_run_id)

        return output


# ── Real LangChain usage ──────────────────────────────────────────────────────

def run_real_langchain(api_key: str, openai_key: str, endpoint: str):
    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate
    from langchain.chains import LLMChain

    sentinel.init(api_key=api_key, endpoint=endpoint)

    # ONE LINE: create the callback
    cb = sentinel.LangChainCallback(workflow_name="LangChain Research Pipeline")

    # Pass it to your LLM — nothing else changes
    llm = ChatOpenAI(model="gpt-4o", openai_api_key=openai_key, callbacks=[cb])

    prompt = ChatPromptTemplate.from_template("Research fintech companies for: {query}")
    chain = LLMChain(llm=llm, prompt=prompt, callbacks=[cb])

    result = chain.run(query="Series B SaaS companies in NYC")
    print(f"Result: {result[:100]}...")
    cb.finish()
    print(f"View at: {endpoint}/dashboard → run_id={cb.run_id}")


# ── Simulated usage ───────────────────────────────────────────────────────────

def run_simulated(api_key: str, endpoint: str):
    sentinel.init(api_key=api_key, endpoint=endpoint)

    # ONE LINE: create the callback
    cb = sentinel.LangChainCallback(workflow_name="LangChain Research Pipeline")
    print(f"run_id: {cb.run_id}")
    print("Passing sentinel.LangChainCallback() to all LangChain components...\n")

    # Pass cb to your existing LangChain LLMs and tools — nothing else changes
    research_llm  = SimulatedLLM(model="gpt-4o",      callbacks=[cb])
    personalize_llm = SimulatedLLM(model="gpt-4o-mini", callbacks=[cb])
    web_search    = SimulatedTool(name="web_search",  callbacks=[cb])
    crm_tool      = SimulatedTool(name="crm_lookup",  callbacks=[cb])

    # Your existing pipeline — completely unchanged
    print("Chain step 1: Web search...")
    search_result = web_search.run("Series B fintech companies 2024")
    print(f"  → {search_result}")

    print("Chain step 2: Research LLM...")
    research = research_llm.invoke(f"Analyse these companies: {search_result}")
    print(f"  → {research[:80]}...")

    print("Chain step 3: CRM lookup...")
    crm_data = crm_tool.run("Acme Corp")
    print(f"  → {crm_data}")

    print("Chain step 4: Personalize LLM...")
    email = personalize_llm.invoke(f"Write outreach using: {research[:100]}, CRM: {crm_data}")
    print(f"  → {email[:80]}...")

    cb.finish()  # mark run as completed

    print(f"\n4 steps (2 LLM calls + 2 tool calls) auto-traced in run: {cb.run_id}")
    print(f"View at: {endpoint}/dashboard → Traces tab")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key",    required=True)
    parser.add_argument("--openai-key", default=None)
    parser.add_argument("--endpoint",   default="https://www.agentsentinelai.com")
    parser.add_argument("--simulate",   action="store_true")
    args = parser.parse_args()

    if args.simulate or not args.openai_key:
        print("Simulated mode (pass --openai-key for real LangChain)\n")
        run_simulated(args.api_key, args.endpoint)
    else:
        run_real_langchain(args.api_key, args.openai_key, args.endpoint)
