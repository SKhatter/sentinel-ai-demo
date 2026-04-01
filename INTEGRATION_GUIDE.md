# Sentinel.AI — Integration Guide

## Install

```bash
pip install sentinelai-sdk
```

## Get an API key

1. Go to **[www.agentsentinelai.com/dashboard](https://www.agentsentinelai.com/dashboard)**
2. Click the **⚙️ gear icon** → enter a key name → **Generate Key**
3. Copy the `sk_live_...` key — shown only once

> Free. No credit card required.

---

## Choose your path

### [Automatic Integration →](INTEGRATION_AUTO.md)

The CLI reads your existing pipeline file, asks what to add, and writes the instrumented version. No manual API knowledge needed.

```bash
sentinel instrument pipeline.py
```

Covers tracing, contracts, and shared state. Recommended for most users.

---

### [Manual Integration →](INTEGRATION_MANUAL.md)

Write the sentinel calls yourself. Full control over exactly what gets added and where.

Use this if:
- The CLI output needs adjustment for your specific setup
- You want to understand exactly what each call does
- You're integrating into a framework with non-standard structure

---

*Sentinel.AI — The Control Plane for AI Agents · https://www.agentsentinelai.com*
