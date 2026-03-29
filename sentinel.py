"""
Sentinel.AI Python SDK
======================
Drop-in reliability observability for multi-agent workflows.

Quickstart:
    import sentinel

    sentinel.init(api_key="sk_live_...", endpoint="https://agentsentinelai.com")

    with sentinel.workflow("My Pipeline") as run:
        with run.step("research-agent", step_type="llm_call") as step:
            result = my_agent.run(query)
            step.set_output({"result": result})

        with run.step("write-agent", step_type="tool_call") as step:
            output = writer.run(result)
            step.set_output({"output": output})

Or use the decorator:
    @sentinel.trace_step(name="research-agent", step_type="llm_call")
    def run_research(query):
        return my_agent.run(query)
"""

import time
import uuid
import threading
import functools
from datetime import datetime, timezone
from typing import Optional, Dict, Any

try:
    import requests as _requests
    _has_requests = True
except ImportError:
    _has_requests = False
    import urllib.request
    import json as _json

# ── Global config ─────────────────────────────────────────────────────────────

_config = {
    "api_key": None,
    "endpoint": "https://agentsentinelai.com",
    "timeout": 5,
    "enabled": True,
}


def init(api_key: str, endpoint: str = "https://agentsentinelai.com", timeout: int = 5):
    """
    Initialize the Sentinel SDK. Call this once at app startup.

    Args:
        api_key:  Your Sentinel API key (sk_live_...).
        endpoint: Sentinel platform URL.
        timeout:  HTTP request timeout in seconds.
    """
    _config["api_key"] = api_key
    _config["endpoint"] = endpoint.rstrip("/")
    _config["timeout"] = timeout
    _config["enabled"] = True


def disable():
    """Disable all telemetry (e.g. in tests)."""
    _config["enabled"] = False


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def _post(path: str, payload: Dict) -> Optional[Dict]:
    """Fire-and-forget POST. Never raises — failures are logged silently."""
    if not _config["enabled"] or not _config["api_key"]:
        return None
    url = _config["endpoint"] + path
    headers = {
        "Authorization": f"Bearer {_config['api_key']}",
        "Content-Type": "application/json",
    }
    try:
        if _has_requests:
            r = _requests.post(url, json=payload, headers=headers, timeout=_config["timeout"])
            return r.json() if r.ok else None
        else:
            data = _json.dumps(payload).encode()
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=_config["timeout"]) as resp:
                return _json.loads(resp.read())
    except Exception:
        return None


def _post_async(path: str, payload: Dict):
    """Send in a background thread so agent code isn't blocked."""
    t = threading.Thread(target=_post, args=(path, payload), daemon=True)
    t.start()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── WorkflowRun ────────────────────────────────────────────────────────────────

class WorkflowStep:
    """
    Context manager for a single step within a workflow run.

    with run.step("research-agent", step_type="llm_call") as step:
        result = agent.run(query)
        step.set_output({"tokens": 120, "result": result})
    """

    def __init__(self, run: "WorkflowRun", name: str, step_type: str = "llm_call",
                 step_id: Optional[str] = None, upstream: Optional[list] = None):
        self.run = run
        self.name = name
        self.step_type = step_type
        self.step_id = step_id or f"step_{uuid.uuid4().hex[:12]}"
        self.upstream = upstream or []
        self._started_at: Optional[str] = None
        self._t0: Optional[float] = None
        self._output: Optional[Dict] = None
        self._input: Optional[Dict] = None

    def set_input(self, data: Any):
        """Optionally record the step's input payload."""
        self._input = data if isinstance(data, dict) else {"value": str(data)}

    def set_output(self, data: Any):
        """Record the step's output payload."""
        self._output = data if isinstance(data, dict) else {"value": str(data)}

    def __enter__(self):
        self._started_at = _now()
        self._t0 = time.time()
        _post_async("/api/ingest/step", {
            "run_id": self.run.run_id,
            "step_id": self.step_id,
            "step_name": self.name,
            "step_type": self.step_type,
            "status": "running",
            "started_at": self._started_at,
            "input": self._input,
            "upstream_step_ids": self.upstream,
        })
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self._t0) * 1000)
        status = "failed" if exc_type else "success"
        error = str(exc_val) if exc_val else None
        _post_async("/api/ingest/step", {
            "run_id": self.run.run_id,
            "step_id": self.step_id,
            "step_name": self.name,
            "step_type": self.step_type,
            "status": status,
            "started_at": self._started_at,
            "completed_at": _now(),
            "duration_ms": duration_ms,
            "input": self._input,
            "output": self._output,
            "error": error,
            "upstream_step_ids": self.upstream,
        })
        return False  # don't suppress exceptions


class WorkflowRun:
    """
    Context manager for a complete workflow run.

    with sentinel.workflow("Customer Outreach Pipeline") as run:
        with run.step("intake-agent") as step:
            ...
    """

    def __init__(self, name: str, run_id: Optional[str] = None, metadata: Optional[Dict] = None):
        self.workflow_name = name
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:16]}"
        self.metadata = metadata or {}
        self._started_at: Optional[str] = None
        self._steps: list = []

    def step(self, name: str, step_type: str = "llm_call",
             step_id: Optional[str] = None, upstream: Optional[list] = None) -> WorkflowStep:
        """
        Create a step within this run.

        Args:
            name:      Human-readable step name (e.g. "research-agent").
            step_type: One of: llm_call, tool_call, agent_handoff, api_call, notification.
            step_id:   Optional stable ID (auto-generated if omitted).
            upstream:  List of step_ids this step depends on.
        """
        s = WorkflowStep(self, name, step_type=step_type, step_id=step_id, upstream=upstream)
        self._steps.append(s)
        return s

    def __enter__(self):
        self._started_at = _now()
        _post_async("/api/ingest/run", {
            "run_id": self.run_id,
            "workflow_name": self.workflow_name,
            "status": "running",
            "started_at": self._started_at,
            "metadata": self.metadata,
        })
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        status = "failed" if exc_type else "completed"
        _post_async("/api/ingest/run", {
            "run_id": self.run_id,
            "workflow_name": self.workflow_name,
            "status": status,
        })
        return False


# ── Top-level helpers ──────────────────────────────────────────────────────────

def workflow(name: str, run_id: Optional[str] = None, metadata: Optional[Dict] = None) -> WorkflowRun:
    """
    Start a new workflow run. Use as a context manager.

    with sentinel.workflow("My Pipeline") as run:
        with run.step("agent-1") as step:
            ...
    """
    return WorkflowRun(name=name, run_id=run_id, metadata=metadata)


def trace_step(name: Optional[str] = None, step_type: str = "llm_call",
               workflow_name: str = "default", run_id: Optional[str] = None):
    """
    Decorator to trace a single function as a workflow step.

    @sentinel.trace_step(name="research-agent", step_type="llm_call")
    def run_research(query: str) -> str:
        return agent.run(query)
    """
    def decorator(fn):
        step_name = name or fn.__name__

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            rid = run_id or f"run_{uuid.uuid4().hex[:16]}"
            _post_async("/api/ingest/run", {
                "run_id": rid,
                "workflow_name": workflow_name,
                "status": "running",
                "started_at": _now(),
            })
            sid = f"step_{uuid.uuid4().hex[:12]}"
            started = _now()
            t0 = time.time()
            _post_async("/api/ingest/step", {
                "run_id": rid, "step_id": sid,
                "step_name": step_name, "step_type": step_type,
                "status": "running", "started_at": started,
            })
            try:
                result = fn(*args, **kwargs)
                duration_ms = int((time.time() - t0) * 1000)
                _post_async("/api/ingest/step", {
                    "run_id": rid, "step_id": sid,
                    "step_name": step_name, "step_type": step_type,
                    "status": "success", "started_at": started,
                    "completed_at": _now(), "duration_ms": duration_ms,
                    "output": {"value": str(result)[:500]},
                })
                _post_async("/api/ingest/run", {"run_id": rid, "workflow_name": workflow_name, "status": "completed"})
                return result
            except Exception as e:
                duration_ms = int((time.time() - t0) * 1000)
                _post_async("/api/ingest/step", {
                    "run_id": rid, "step_id": sid,
                    "step_name": step_name, "step_type": step_type,
                    "status": "failed", "started_at": started,
                    "completed_at": _now(), "duration_ms": duration_ms,
                    "error": str(e),
                })
                _post_async("/api/ingest/run", {"run_id": rid, "workflow_name": workflow_name, "status": "failed"})
                raise

        return wrapper
    return decorator


# ── Atomic State Coordination ──────────────────────────────────────────────────

class ConflictError(Exception):
    """Raised when a propose() fails due to a version conflict."""
    def __init__(self, message, current_value=None, current_version=None):
        super().__init__(message)
        self.current_value = current_value
        self.current_version = current_version


def get_state(namespace: str, key: str) -> tuple:
    """
    Read shared state. Returns (value, version).

    value is None and version is 0 if the key doesn't exist yet.

    Example:
        profile, version = sentinel.get_state("run_001", "lead_profile")
    """
    result = _post(f"/api/state/{namespace}/{key}", {})
    # GET not POST — use direct call
    if not _config["enabled"] or not _config["api_key"]:
        return None, 0
    url = _config["endpoint"] + f"/api/state/{namespace}/{key}"
    headers = {"Authorization": f"Bearer {_config['api_key']}"}
    try:
        if _has_requests:
            r = _requests.get(url, headers=headers, timeout=_config["timeout"])
            data = r.json()
        else:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=_config["timeout"]) as resp:
                data = _json.loads(resp.read())
        return data.get("value"), data.get("version", 0)
    except Exception:
        return None, 0


def propose_state(namespace: str, key: str, value: Any, base_version: int,
                  agent_name: Optional[str] = None) -> int:
    """
    Atomically update shared state using compare-and-swap.

    Commits only if the current version == base_version.
    Raises ConflictError if another agent has already written a newer version.

    Returns the new version number on success.

    Example:
        profile, version = sentinel.get_state("run_001", "lead_profile")
        updated = process(profile)
        new_version = sentinel.propose_state("run_001", "lead_profile", updated, base_version=version)
    """
    if not _config["enabled"] or not _config["api_key"]:
        return base_version + 1

    url = _config["endpoint"] + f"/api/state/{namespace}/{key}/propose"
    headers = {
        "Authorization": f"Bearer {_config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {"value": value, "base_version": base_version, "agent_name": agent_name}
    try:
        if _has_requests:
            r = _requests.post(url, json=payload, headers=headers, timeout=_config["timeout"])
            data = r.json()
            if r.status_code == 409:
                cur = data.get("current", {})
                raise ConflictError(
                    data.get("message", "Version conflict"),
                    current_value=cur.get("value"),
                    current_version=cur.get("version"),
                )
            return data.get("version", base_version + 1)
        else:
            body = _json.dumps(payload).encode()
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=_config["timeout"]) as resp:
                    data = _json.loads(resp.read())
                    return data.get("version", base_version + 1)
            except urllib.error.HTTPError as e:
                if e.code == 409:
                    data = _json.loads(e.read())
                    cur = data.get("current", {})
                    raise ConflictError(
                        data.get("message", "Version conflict"),
                        current_value=cur.get("value"),
                        current_version=cur.get("version"),
                    )
                raise
    except ConflictError:
        raise
    except Exception as e:
        raise RuntimeError(f"propose_state failed: {e}") from e


def propose_state_with_retry(namespace: str, key: str, update_fn, agent_name: Optional[str] = None,
                              max_retries: int = 3) -> int:
    """
    Read-process-propose with automatic retry on conflict.

    update_fn receives the current value and returns the new value.
    Retries up to max_retries times if a conflict is detected.

    Example:
        def add_result(current):
            current = current or {}
            current["research"] = {"summary": "...", "score": 0.9}
            return current

        sentinel.propose_state_with_retry("run_001", "shared_context", add_result)
    """
    for attempt in range(max_retries + 1):
        value, version = get_state(namespace, key)
        new_value = update_fn(value)
        try:
            return propose_state(namespace, key, new_value, base_version=version, agent_name=agent_name)
        except ConflictError:
            if attempt == max_retries:
                raise
            time.sleep(0.05 * (2 ** attempt))  # exponential backoff: 50ms, 100ms, 200ms
    return version


# ── Agent Contracts & Handoff Validation ──────────────────────────────────────

class ContractViolationError(Exception):
    """Raised when a handoff payload violates the receiving agent's contract."""
    def __init__(self, message, from_agent=None, to_agent=None, violations=None, checkpoint_id=None):
        super().__init__(message)
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.violations = violations or []
        self.checkpoint_id = checkpoint_id


def register_contract(agent: str, accepts: Dict = None, produces: Dict = None,
                       description: str = None):
    """
    Register an agent's input/output contract with Sentinel.

    Sentinel will validate all incoming handoff payloads against `accepts`
    before delivering them to this agent.

    Schema field options:
        type:        "string" | "number" | "boolean" | "array" | "object"
        required:    True | False
        min/max:     numeric bounds
        min_length/max_length: string length bounds
        enum:        list of allowed values
        pattern:     regex string

    Example:
        sentinel.register_contract(
            agent="personalize-agent",
            accepts={
                "lead_id":  {"type": "string", "required": True},
                "company":  {"type": "string", "required": True},
                "score":    {"type": "number", "min": 0, "max": 1}
            },
            produces={
                "email_draft": {"type": "string", "max_length": 2000},
                "confidence":  {"type": "number", "min": 0, "max": 1}
            }
        )
    """
    result = _post(f"/api/contracts/{agent}", {
        "accepts": accepts or {},
        "produces": produces or {},
        "description": description
    })
    return result


def handoff(from_agent: str, to_agent: str, payload: Dict,
            run_id: str = None, checkpoint_id: str = None):
    """
    Pass a payload from one agent to another through Sentinel.

    Sentinel validates the payload against `to_agent`'s registered contract.
    If validation fails, raises ContractViolationError — the handoff is
    blocked and an incident is created. Agent B never sees the bad payload.

    If no contract is registered for `to_agent`, the handoff is accepted as-is.

    Example:
        # Agent A finishes, hands off to Agent B
        result = sentinel.handoff(
            from_agent="research-agent",
            to_agent="personalize-agent",
            run_id=run.run_id,
            payload={
                "lead_id": "acme_001",
                "company": "Acme Corp",
                "score": 0.87
            }
        )
        # If payload violates contract → ContractViolationError raised here
        # Agent B never runs with bad data
    """
    if not _config["enabled"] or not _config["api_key"]:
        return {"ok": True, "status": "accepted"}

    url = _config["endpoint"] + "/api/handoff"
    headers = {
        "Authorization": f"Bearer {_config['api_key']}",
        "Content-Type": "application/json",
    }
    body = {
        "from_agent": from_agent,
        "to_agent": to_agent,
        "payload": payload,
        "run_id": run_id,
        "checkpoint_id": checkpoint_id,
    }
    try:
        if _has_requests:
            r = _requests.post(url, json=body, headers=headers, timeout=_config["timeout"])
            data = r.json()
            if r.status_code == 422:
                raise ContractViolationError(
                    data.get("message", "Contract violation"),
                    from_agent=from_agent,
                    to_agent=to_agent,
                    violations=data.get("violations", []),
                    checkpoint_id=data.get("checkpoint_id")
                )
            return data
        else:
            import json as _j
            req_obj = urllib.request.Request(url, data=_j.dumps(body).encode(), headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req_obj, timeout=_config["timeout"]) as resp:
                    return _j.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code == 422:
                    data = _j.loads(e.read())
                    raise ContractViolationError(
                        data.get("message", "Contract violation"),
                        from_agent=from_agent,
                        to_agent=to_agent,
                        violations=data.get("violations", []),
                        checkpoint_id=data.get("checkpoint_id")
                    )
                raise
    except ContractViolationError:
        raise
    except Exception as e:
        raise RuntimeError(f"handoff failed: {e}") from e


def validate_payload(agent: str, payload: Dict) -> Dict:
    """
    Dry-run validate a payload against an agent's contract without triggering a handoff.
    Returns {"valid": True} or {"valid": False, "violations": [...]}.
    """
    if not _config["enabled"] or not _config["api_key"]:
        return {"valid": True}
    url = _config["endpoint"] + f"/api/contracts/{agent}/validate"
    headers = {
        "Authorization": f"Bearer {_config['api_key']}",
        "Content-Type": "application/json",
    }
    try:
        if _has_requests:
            r = _requests.post(url, json={"payload": payload}, headers=headers, timeout=_config["timeout"])
            return r.json()
        else:
            import json as _j
            req_obj = urllib.request.Request(url, data=_j.dumps({"payload": payload}).encode(),
                                             headers=headers, method="POST")
            with urllib.request.urlopen(req_obj, timeout=_config["timeout"]) as resp:
                return _j.loads(resp.read())
    except Exception:
        return {"valid": True}  # fail open — don't block agents if Sentinel is unreachable
