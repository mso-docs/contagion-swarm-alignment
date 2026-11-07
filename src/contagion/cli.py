import argparse
import asyncio
import json
import os
from pathlib import Path

import yaml
import httpx

from .analysis import analyze
from .config import RunConfig, configured_model, load_config
from .controller import run
from .inference import HTTPProvider, MockProvider, OllamaProvider


def provider_for(args, config):
    if args.provider == "mock":
        return MockProvider()
    endpoint = os.environ.get("CONTAGION_BASE_URL")
    if not endpoint:
        raise ValueError("Set CONTAGION_BASE_URL to the operator-approved model endpoint")
    cls = OllamaProvider if args.provider == "ollama" else HTTPProvider
    return cls(endpoint, timeout=config.request_timeout_seconds, retries=config.retries, api=args.provider)


async def execute(args):
    if args.command == "doctor":
        endpoint = os.environ.get("CONTAGION_BASE_URL")
        if not endpoint:
            raise ValueError("No endpoint configured. Set CONTAGION_BASE_URL and CONTAGION_MODEL; no live inference attempted")
        provider = HTTPProvider(endpoint, timeout=5, retries=0, api=args.provider)
        try:
            models = await provider.discover()
            # Explicitly whitelist fields; endpoint addresses and credentials never printed.
            installed = [{"name": m.get("name", m.get("id")), "digest": m.get("digest")} for m in models]
            print(json.dumps({"reachable": True, "installed_models": installed}, indent=2))
            model = os.environ.get("CONTAGION_MODEL")
            if args.check_chat:
                if not model or model not in [m["name"] for m in installed]:
                    raise ValueError("Select an installed CONTAGION_MODEL before --check-chat")
                # Use the authoritative runner, so even this single smoke request is recorded.
                config = RunConfig(protocol_version="1.1" if args.thinking != "default" else "1.0", thinking=args.thinking, model=model, rounds=1, max_model_calls=1, max_wall_seconds=90, request_timeout_seconds=60, retries=0)
                provider.client.timeout = httpx.Timeout(config.request_timeout_seconds)
                provider.identity.update(model=model, digest=next(m["digest"] for m in installed if m["name"] == model))
                path = await run(config, provider, args.out)
                manifest = json.loads((path / "manifest.json").read_text())
                print(f"Chat smoke trace: {path} ({manifest['completed_model_calls']} successful requests; intentionally one-call budget)")
                if not manifest["completed_model_calls"] or manifest["failures"]:
                    raise ValueError("Live chat or output parsing did not validate; inspect smoke trace")
        finally:
            await provider.close()
        return
    if args.command == "analyze":
        rows = analyze(args.source, args.out)
        print(f"Analyzed {len(rows)} completed runs into {args.out}")
        return
    if args.command == "batch":
        data = yaml.safe_load(Path(args.config).read_text())
        allowed = {"base", "topologies", "interventions", "seeds"}
        if set(data) != allowed:
            raise ValueError("Batch config requires base, topologies, interventions, seeds")
        configs = [RunConfig(**{**data["base"], "topology": t, "intervention": i, "seed": s})
                   for t in data["topologies"] for s in data["seeds"] for i in data["interventions"]]
    else:
        configs = [load_config(args.config)]
    configs = [configured_model(c, args.provider) for c in configs]
    provider = provider_for(args, configs[0])
    try:
        if args.provider != "mock":
            installed = await provider.discover()
            model = configs[0].model
            selected = [m for m in installed if m.get("name", m.get("id")) == model]
            if not selected:
                raise ValueError("Configured model is not installed; no automatic pull performed")
            provider.identity.update(model=model, digest=selected[0].get("digest"))
        for config in configs:
            path = await run(config, provider, args.out)
            manifest = json.loads((path / "manifest.json").read_text())
            print(f"{path}: {manifest['status']}")
            if manifest["status"] != "completed":
                raise ValueError("Run did not complete; stopping before further experiment calls")
    finally:
        if hasattr(provider, "close"):
            await provider.close()


def main():
    parser = argparse.ArgumentParser(description="Contagion bounded synthetic research runner")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["run", "batch"]:
        command = commands.add_parser(name)
        command.add_argument("--config", required=True)
        command.add_argument("--provider", choices=["mock", "ollama", "openai"], default="mock")
        command.add_argument("--out", default="results/raw")
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--provider", choices=["ollama", "openai"], default="ollama")
    doctor.add_argument("--thinking", choices=["default", "disabled", "enabled"], default="default")
    doctor.add_argument("--check-chat", action="store_true")
    doctor.add_argument("--out", default="results/smoke")
    analysis = commands.add_parser("analyze")
    analysis.add_argument("--source", default="results/raw")
    analysis.add_argument("--out", default="results/derived")
    args = parser.parse_args()
    try:
        asyncio.run(execute(args))
    except (Exception, KeyboardInterrupt) as exc:
        # HTTP exceptions can contain private endpoint URLs; never echo them.
        if isinstance(exc, httpx.HTTPError):
            safe = f"Model endpoint unavailable ({type(exc).__name__}); verify endpoint and trusted network access"
        else:
            safe = str(exc) if isinstance(exc, ValueError) and not exc.__class__.__module__.startswith("pydantic") else type(exc).__name__
        parser.exit(1, f"Error: {safe}\n")


if __name__ == "__main__":
    main()
