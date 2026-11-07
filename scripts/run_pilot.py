#!/usr/bin/env python3
"""Load operator configuration as data and run the bounded RQ1 pilot workflow."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
KEYS = {
    "CONTAGION_BASE_URL", "CONTAGION_MODEL", "CONTAGION_API_KEY",
    "CONTAGION_PROVIDER", "CONTAGION_PILOT_CONFIG", "CONTAGION_RESULTS_DIR",
    "PRIMARY_SERVER_ID", "SECONDARY_SERVER_ID", "PRIMARY_PROJECT_DIR", "SECONDARY_PROJECT_DIR",
}


def load_env(path, inherited):
    """Small .env grammar: KEY=value with optional quotes/comments; no expansion/execution."""
    values = {}
    if path.exists():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            key, separator, value = line.partition("=")
            if not separator or key.strip() not in KEYS:
                raise ValueError(f"Unsupported .env assignment on line {number}; see .env.example")
            try:
                parts = shlex.split(value, comments=True, posix=True)
            except ValueError:
                raise ValueError(f"Invalid .env quoting on line {number}") from None
            if len(parts) > 1:
                raise ValueError(f"Quote values containing spaces on .env line {number}")
            values[key.strip()] = parts[0] if parts else ""
    # Existing shell variables take precedence, including explicitly empty values.
    return {**values, **inherited}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--provider", choices=["ollama", "openai", "mock"])
    parser.add_argument("--doctor-only", action="store_true", help="List installed models without chat or experiments")
    parser.add_argument("--config", type=Path, help="Override paired pilot YAML")
    parser.add_argument("--export-dashboard", action="store_true", help="Refresh public summary after the pilot")
    parser.add_argument("--out", type=Path, help="Override CONTAGION_RESULTS_DIR")
    args = parser.parse_args(argv)
    try:
        if not args.env_file.exists() and args.env_file != ROOT / ".env":
            raise ValueError("Requested env file does not exist")
        env = load_env(args.env_file, os.environ)
        provider = args.provider or env.get("CONTAGION_PROVIDER") or "ollama"
        if provider not in {"ollama", "openai", "mock"}:
            raise ValueError("CONTAGION_PROVIDER must be ollama, openai, or mock")
        out = args.out or Path(env.get("CONTAGION_RESULTS_DIR") or f"results/{provider}-pilot")
        if not out.is_absolute():
            out = ROOT / out
        config = args.config or Path(env.get("CONTAGION_PILOT_CONFIG") or "configs/rq1_pair.yaml")
        if not config.is_absolute():
            config = ROOT / config

        def step(label, *arguments):
            print(label, flush=True)
            subprocess.run([sys.executable, "-m", "contagion.cli", *map(str, arguments)],
                           cwd=ROOT, env=env, check=True)

        if provider != "mock":
            if not env.get("CONTAGION_BASE_URL"):
                raise ValueError("Copy .env.example to .env and set CONTAGION_BASE_URL first")
            step("Checking endpoint and listing installed models…", "doctor", "--provider", provider)
            if args.doctor_only:
                return 0
            if not env.get("CONTAGION_MODEL"):
                raise ValueError("Set CONTAGION_MODEL in .env to an installed tag listed above, then rerun")
            import yaml
            thinking = yaml.safe_load(config.read_text()).get("base", {}).get("thinking", "default")
            step("Validating one logged chat response…", "doctor", "--provider", provider,
                 "--check-chat", "--thinking", thinking, "--out", out / "smoke")
        elif args.doctor_only:
            raise ValueError("--doctor-only requires a live provider (ollama or openai)")
        if not config.is_file():
            raise ValueError("Pilot config does not exist; check CONTAGION_PILOT_CONFIG")
        step(f"Running bounded paired pilot ({provider})…", "batch", "--config", config,
             "--provider", provider, "--out", out / "raw")
        step("Generating analysis from recorded events…", "analyze", "--source", out / "raw",
             "--out", out / "derived")
        if args.export_dashboard:
            print("Exporting public summary (free-text traces withheld)…", flush=True)
            subprocess.run([sys.executable, str(ROOT / "scripts/export_dashboard.py"),
                            "--source", str(out / "raw"), "--env-file", str(args.env_file)],
                           cwd=ROOT, env=env, check=True)
        print(f"Pilot finished. Review {out / 'derived' / 'manual_review.json'} and plots.")
        print("The full 18-run batch is a separate step after reviewing the pilot.")
        if provider == "mock":
            print("MOCK ONLY: this validates software, not real-model behavior.")
        return 0
    except subprocess.CalledProcessError:
        print("Pilot stopped because a step failed; later steps were not run. See the diagnostic above.", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        # Never echo .env values or exception strings containing endpoint/credential data.
        message = str(exc) if isinstance(exc, ValueError) else "Could not read configuration or launch the Python CLI"
        print(f"Error: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
