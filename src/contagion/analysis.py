"""Regenerate all RQ1 summaries from checksummed source events, never cached scores."""
import csv
import json
import os
from collections import defaultdict
from pathlib import Path

from .config import RunConfig
from .events import read_events
from .scoring import score
from .storage import verify
from .topology import adjacency


def analyze(source, out):
    directories = sorted(Path(source).glob("*/manifest.json"))
    rows, trajectories, examples = [], [], []
    for manifest_path in directories:
        directory = manifest_path.parent
        if not verify(directory):
            raise ValueError(f"Checksum validation failed: {directory.name}")
        manifest = json.loads(manifest_path.read_text())
        if manifest["status"] != "completed":
            continue
        config = RunConfig(**json.loads((directory / "config.snapshot.json").read_text()))
        events = read_events(directory / "events.jsonl")
        outcome = score(events, config, adjacency(config.topology), directory.name)
        row = {"run_id": directory.name, "backend": manifest["model_identity"]["backend"],
               "model": config.model, "protocol_version": config.protocol_version,
               "topology": config.topology, "intervention": config.intervention, "seed": config.seed,
               **{k: v for k, v in outcome.items() if k not in {"agents", "run_id"}}}
        rows.append(row)
        for round_no in range(config.rounds):
            partial = score([e for e in events if e["round"] <= round_no], config, adjacency(config.topology), directory.name)
            trajectories.append({"run_id": directory.name, "round": round_no, "topology": config.topology,
                                 "intervention": config.intervention, "backend": row["backend"], "model": row["model"],
                                 "rate": partial["downstream_adoption_rate"]})
        for event in events:
            if event["event_type"] in {"artifact", "parse_failure"}:
                examples.append({"run_id": directory.name, "event_id": event["event_id"], "agent_id": event["agent_id"],
                                 "round": event["round"], "type": event["event_type"], "text": event["content"]})
    if not rows:
        raise ValueError("No completed, checksummed RQ1 runs; no plots generated")
    condition_keys = [(r["topology"], r["intervention"], r["seed"]) for r in rows]
    if len(set(condition_keys)) != len(condition_keys):
        raise ValueError("Duplicate run conditions: use separate sources for protocol/source revisions")
    cohorts = {(r["backend"], r["model"], r["protocol_version"]) for r in rows}
    if len(cohorts) != 1:
        raise ValueError("Mixed backend/model/protocol cohorts: analyze separate source directories")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "runs.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (out / "manual_review.json").write_text(json.dumps(examples, indent=2))
    os.environ.setdefault("MPLCONFIGDIR", str(out.resolve() / ".matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["topology"], row["intervention"])].append(row)
    keys = sorted(grouped)
    labels = [f"{t}\n{i}" for t, i in keys]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    for ax, field, title in zip(axes, ["downstream_adoption_rate", "legitimate_task_success_rate", "messages_delivered"],
                               ["Final downstream adoption", "Strict task success", "Delivered messages (exposure confound)"]):
        for index, key in enumerate(keys):
            values = [r[field] for r in grouped[key]]
            ax.scatter([index + (j - (len(values) - 1) / 2) * .05 for j in range(len(values))], values)
            ax.plot([index - .15, index + .15], [sum(values) / len(values)] * 2, color="black")
        ax.set_xticks(range(len(keys)), labels, rotation=35, fontsize=7)
        ax.set_title(title, fontsize=10)
    label = "MOCK — SOFTWARE VALIDATION ONLY" if rows[0]["backend"] == "mock" else "Exploratory RQ1; runs are analysis units"
    fig.suptitle(label)
    fig.tight_layout()
    fig.savefig(out / "rq1_summary.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    for key in keys:
        selected = [r for r in trajectories if (r["topology"], r["intervention"]) == key]
        rounds = sorted({r["round"] for r in selected})
        rates = [sum(r["rate"] for r in selected if r["round"] == t) / sum(r["round"] == t for r in selected) for t in rounds]
        ax.plot(rounds, rates, marker="o", label=" / ".join(key))
    ax.set(xlabel="Round (zero-based)", ylabel="Mean downstream artifact adoption", title=label)
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "rq1_rounds.png", dpi=160)
    plt.close(fig)
    (out / "analysis_notes.txt").write_text(
        f"{label}\n{len(rows)} completed run-condition combinations; paired seeds are dependent.\n"
        "Points are run-level values; black bars are means, not confidence intervals.\n"
        "No statistical power or real-world compromise claims. Topology changes exposure.\n"
        "Exact suffix scorer is conservative; inspect manual_review.json for ambiguous cases.\n")
    return rows
