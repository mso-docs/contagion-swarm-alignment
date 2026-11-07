import asyncio
import copy
import platform
import subprocess
import time

from . import __version__
from .agents import Agent, SYSTEM_PROMPT, TASK
from .config import digest
from .events import EventRecorder, read_events, utc
from .interventions import intervene
from .inference import CallBudgetExhausted
from .models import Artifact, SamplingConfig
from .scoring import score
from .storage import allocate, seal, source_fingerprint, write_json
from .topology import adjacency


async def run(config, provider, root="results/raw"):
    directory, skipped = allocate(root, config, provider.identity)
    if skipped:
        return directory
    started, clock_start = utc(), time.monotonic()
    graph = adjacency(config.topology)
    agents = {name: Agent(name) for name in graph}
    recorder = EventRecorder(directory / "events.jsonl", directory.name)
    write_json(directory / "config.snapshot.json", config.model_dump())
    calls, http_calls, failures, status = 0, 0, [], "completed"
    inbox = {name: [] for name in graph}
    recorder.emit("run_started", metadata={"graph": graph})
    try:
        for round_no in range(config.rounds):
            pending = {name: [] for name in graph}
            for name, agent in agents.items():
                remaining = config.max_wall_seconds - (time.monotonic() - clock_start)
                consumed = http_calls if hasattr(provider, "audit") else calls
                if consumed >= config.max_model_calls or remaining <= 0:
                    status = "budget_exhausted"
                    break
                for delivered in inbox[name]:
                    recorder.emit("message_delivered", round_no, **delivered)
                agent.receive(inbox[name], round_no)
                sampling = SamplingConfig(model=config.model, thinking=config.thinking, seed=config.seed + round_no * 5 + int(name[-1]),
                                          temperature=config.temperature, max_output_tokens=config.max_output_tokens)
                recorder.emit("inference_requested", round_no, agent_id=name,
                              metadata={"messages": copy.deepcopy(agent.private_history), "sampling": sampling.model_dump(), "invocation_order": calls})
                calls += 1
                call_start = time.monotonic()
                def audit(kind, metadata):
                    nonlocal http_calls
                    if kind == "http_attempt":
                        if http_calls >= config.max_model_calls:
                            raise CallBudgetExhausted()
                        http_calls += 1
                    recorder.emit(kind, round_no, agent_id=name, metadata=metadata)
                if hasattr(provider, "audit"):
                    provider.audit = audit
                try:
                    response = await asyncio.wait_for(provider.chat(copy.deepcopy(agent.private_history), sampling), timeout=remaining)
                except (asyncio.TimeoutError, CallBudgetExhausted) as exc:
                    status = "budget_exhausted"
                    reason = "wall_budget" if isinstance(exc, asyncio.TimeoutError) else "http_call_budget"
                    recorder.emit("inference_failure", round_no, agent_id=name, metadata={"reason": reason})
                    failures.append(reason)
                    break
                recorder.emit("inference_response", round_no, agent_id=name, content=response.content,
                              metadata={**response.metadata, "duration_seconds": time.monotonic() - call_start})
                agent.private_history.append({"role": "assistant", "content": response.content})
                try:
                    artifact = Artifact.model_validate_json(response.content)
                except ValueError:
                    recorder.emit("parse_failure", round_no, agent_id=name, content=response.content)
                    failures.append("parse_failure")
                    # A malformed last response must not fall back to an earlier valid answer.
                    recorder.emit("artifact", round_no, agent_id=name, content="")
                    continue
                recorder.emit("artifact", round_no, agent_id=name, content=artifact.answer)
                generated = recorder.emit("message_generated", round_no, sender_id=name, content=artifact.message)
                message_id = generated["event_id"]
                routed = intervene(artifact.message, config, name, round_no)
                if routed != artifact.message:
                    recorder.emit("intervention_applied", round_no, sender_id=name, parent_message_id=message_id,
                                  content=routed, metadata={"original": artifact.message, "intervention_id": "benign-marker-v1"})
                # Last-round messages are recorded as generated but have no delivery phase.
                if round_no + 1 < config.rounds:
                    for receiver in graph[name]:
                        pending[receiver].append({"sender_id": name, "receiver_id": receiver,
                                                  "message_id": f"{message_id}->{receiver}",
                                                  "parent_message_id": message_id, "content": routed})
            if status != "completed":
                break
            inbox = pending
        if failures and status == "completed":
            status = "failed"
    except (Exception, asyncio.CancelledError, KeyboardInterrupt) as exc:
        status = "failed"
        failures.append(type(exc).__name__)
        recorder.emit("run_failure", metadata={"reason": type(exc).__name__})
    if hasattr(provider, "audit"):
        provider.audit = None
    recorder.emit("run_finished", metadata={"status": status, "model_calls": calls})
    recorder.close()
    events = read_events(directory / "events.jsonl")
    write_json(directory / "outcome.json", score(events, config, graph, directory.name))
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=2).stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        commit = None
    write_json(directory / "manifest.json", {
        "run_id": directory.name, "status": status, "started_utc": started, "ended_utc": utc(),
        "duration_seconds": time.monotonic() - clock_start, "package_version": __version__, "commit_sha": commit,
        "config_hash": digest(config.model_dump()), "protocol_hash": digest({"version": config.protocol_version, "system": SYSTEM_PROMPT, "task": TASK}),
        "source_hash": source_fingerprint(),
        "model_identity": provider.identity, "sampling": {"temperature": config.temperature, "max_output_tokens": config.max_output_tokens, "seed": config.seed},
        "environment": {"python": platform.python_version(), "os": platform.system(), "machine": platform.machine()},
        "graph": graph, "completed_model_calls": sum(e["event_type"] == "inference_response" for e in events),
        "attempted_model_calls": calls, "http_attempts": http_calls, "failures": failures,
        "intervention_id": "benign-marker-v1" if config.intervention != "none" else None,
        "limitations": "Mock fixtures are not empirical LLM results; live seed determinism is unverified.",
    })
    seal(directory)
    return directory
