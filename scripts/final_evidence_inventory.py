#!/usr/bin/env python3
"""Freeze a metadata-only final inventory; never changes the paper's original cutoff."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from contagion.config import digest
from contagion.publication import validate_snapshot
from contagion.research_publication import validate_research_snapshot
from contagion.storage import verify

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from repository_publication import validate_repository_snapshot
from followup_publication import validate as validate_followups
from scan_privacy import scan_blob


class Closed(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Entry(Closed):
    index: Literal['results', 'research', 'repositories', 'followups', 'multidomain', 'diversity']
    id: str = Field(pattern=r'^[a-f0-9]{16}$')
    protocol: str = Field(max_length=100)
    model: str = Field(max_length=160)
    backend: Literal['mock', 'ollama', 'openai']
    family: str = Field(max_length=80)
    phase: str = Field(max_length=80)
    condition: str = Field(max_length=80)
    status: Literal['completed', 'failed', 'budget_exhausted']
    calls: int = Field(ge=0)
    rounds: int | None = Field(default=None, ge=0)
    agents: int | None = Field(default=None, ge=1)
    topology: str = Field(max_length=30)
    source_seal: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    trajectory_hash: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    retained_failed_attempts: int = Field(default=0, ge=0)
    memory_policy: str | None = Field(default=None, max_length=160)
    context_selection: str | None = Field(default=None, max_length=160)

    @model_validator(mode='after')
    def lineage_pair(self):
        if (self.source_seal is None) != (self.trajectory_hash is None):
            raise ValueError('Seal and trajectory evidence must be paired')
        return self


class Counts(Closed):
    indexed_rows: int
    live_rows: int
    live_completed_rows: int
    mock_rows: int
    lineage_verified_rows: int
    unmatched_rows: int
    distinct_verified_trajectories: int
    duplicate_index_rows: int
    live_distinct_verified_trajectories: int
    live_distinct_completed_trajectories: int
    live_distinct_returned_responses: int
    mock_distinct_verified_trajectories: int
    trained_neural_captures: int
    random_neural_checks: int
    monitor_cells: int
    advisory_reviews: int
    diversity_records: int


class Inventory(Closed):
    schema_version: Literal['final-evidence-inventory-1.0'] = 'final-evidence-inventory-1.0'
    supplement_only: Literal[True] = True
    software_tests_passed: int = Field(ge=0)
    input_sha256: dict[Literal['results', 'research', 'repositories', 'followups'], Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]]
    snapshot_generated_utc: dict[Literal['results', 'research', 'repositories', 'followups'], str]
    counts: Counts
    runs: list[Entry]


def raw_index(root):
    """Resolve public identifiers privately; only matching, sealed sources are read later."""
    mapping = {}
    for path in Path(root).rglob('manifest.json'):
        directory = path.parent
        if not (directory / 'checksum.sha256').is_file() or not (directory / 'events.jsonl').is_file():
            continue
        try:
            manifest = json.loads(path.read_text())
            run_id = manifest.get('run_id')
            identifiers = {digest(str(directory.resolve()))[:16]}
            if isinstance(run_id, str):
                identifiers.update({digest(run_id)[:16], hashlib.sha256(run_id.encode()).hexdigest()[:16]})
            # Original protocol1 public IDs include directory name and event digest.
            if manifest.get('protocol_version') == '1.0' or manifest.get('protocol_hash'):
                fingerprint = hashlib.sha256((directory / 'events.jsonl').read_bytes()).hexdigest()
                identifiers.add(hashlib.sha256((directory.name + fingerprint).encode()).hexdigest()[:16])
            for identifier in identifiers:
                mapping.setdefault(identifier, []).append(directory)
        except (OSError, ValueError, TypeError):
            continue
    return mapping


def reconcile(entry, mapping):
    candidates = mapping.get(entry.id, [])
    if not candidates:
        return entry
    evidence = []
    for directory in candidates:
        if not verify(directory):
            raise ValueError('Matching source failed checksum validation')
        manifest = json.loads((directory / 'manifest.json').read_text())
        events = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines() if line]
        calls = sum(event['event_type'] == 'inference_response' for event in events)
        if calls != entry.calls or manifest.get('status') != entry.status:
            raise ValueError('Public/source counters or status disagree')
        evidence.append((hashlib.sha256((directory / 'events.jsonl').read_bytes()).hexdigest(),
                         hashlib.sha256((directory / 'checksum.sha256').read_bytes()).hexdigest()))
    if len({fingerprint for fingerprint, _ in evidence}) != 1:
        raise ValueError('Ambiguous public identifier resolves to different trajectories')
    return entry.model_copy(update={'trajectory_hash': evidence[0][0], 'source_seal': evidence[0][1]})


def build(data_root, raw_root, software_tests=499, env=None):
    data_root = Path(data_root)
    files = {name: data_root / f'{name}.json' for name in ['results', 'research', 'repositories', 'followups']}
    validate_snapshot(files['results'], env=env)
    validate_research_snapshot(files['research'], env=env)
    validate_repository_snapshot(files['repositories'], env or {})
    validate_followups(files['followups'], env=env)
    data = {name: json.loads(path.read_text()) for name, path in files.items()}
    mapping = raw_index(raw_root)
    rows = []
    sources = [('results', data['results']['runs']), ('research', data['research']['studies']),
               ('repositories', data['repositories']['runs']), ('followups', data['followups']['runs']),
               ('multidomain', data['followups'].get('multidomain', [])), ('diversity', data['followups'].get('diversity', []))]
    for index, values in sources:
        for row in values:
            entry = Entry(index=index, id=row['id'], protocol=row.get('protocol', row.get('protocol_version')),
                model=row['model'], backend=row['backend'], family=row.get('domain', row.get('task_family', 'catalog')),
                phase=row.get('phase', row.get('split', 'legacy_unspecified')),
                condition=row.get('arm', row.get('intervention', 'not_recorded')), status=row['status'],
                calls=row.get('calls', row.get('completed_calls')), rounds=row.get('rounds'),
                agents=row.get('agent_count', len(row.get('agents', [])) or None), topology=row['topology'],
                retained_failed_attempts=row.get('retained_failed_attempts', 0), memory_policy=row.get('memory_policy'), context_selection=row.get('context_selection'))
            rows.append(reconcile(entry, mapping))
    unique = {}
    for row in rows:
        if row.trajectory_hash:
            previous = unique.setdefault(row.trajectory_hash, row)
            if (previous.backend, previous.calls, previous.status) != (row.backend, row.calls, row.status):
                raise ValueError('Duplicate trajectory has conflicting metadata')
    live = [row for row in unique.values() if row.backend != 'mock']
    neural = data['research']['neural']
    counts = Counts(indexed_rows=len(rows), live_rows=sum(r.backend != 'mock' for r in rows),
        live_completed_rows=sum(r.backend != 'mock' and r.status == 'completed' for r in rows),
        mock_rows=sum(r.backend == 'mock' for r in rows), lineage_verified_rows=sum(r.trajectory_hash is not None for r in rows),
        unmatched_rows=sum(r.trajectory_hash is None for r in rows), distinct_verified_trajectories=len(unique),
        duplicate_index_rows=sum(r.trajectory_hash is not None for r in rows)-len(unique),
        live_distinct_verified_trajectories=len(live), live_distinct_completed_trajectories=sum(r.status == 'completed' for r in live),
        live_distinct_returned_responses=sum(r.calls for r in live), mock_distinct_verified_trajectories=sum(r.backend == 'mock' for r in unique.values()),
        trained_neural_captures=sum(r['evidence_type'] == 'instrumented_checkpoint_replay' for r in neural),
        random_neural_checks=sum(r['evidence_type'] == 'random_weight_smoke' for r in neural),
        monitor_cells=len(data['research']['monitor'])+len(data['followups']['monitor']),
        advisory_reviews=len(data['research']['reviews'])+len(data['followups']['reviews']),
        diversity_records=len(data['followups'].get('diversity', [])))
    inventory = Inventory(software_tests_passed=software_tests, snapshot_generated_utc={k: value['generated_utc'] for k,value in data.items()}, input_sha256={k: hashlib.sha256(p.read_bytes()).hexdigest() for k,p in files.items()}, counts=counts, runs=rows)
    if scan_blob(inventory.model_dump_json().encode(), public=True):
        raise ValueError('Inventory privacy validation failed')
    return inventory


def validate_inventory(path, env=None, data_root=None):
    """Validate closed public metadata without loading raw sources or making calls."""
    from contagion.publication import sensitive_values
    value = Inventory.model_validate_json(Path(path).read_text())
    if set(value.input_sha256) != {'results', 'research', 'repositories', 'followups'} or set(value.snapshot_generated_utc) != set(value.input_sha256):
        raise ValueError('Four exact public snapshot inputs required')
    if any(count < 0 for count in value.counts.model_dump().values()):
        raise ValueError('Negative inventory count')
    if value.counts.indexed_rows != len(value.runs) or value.counts.live_rows + value.counts.mock_rows != len(value.runs):
        raise ValueError('Inventory row denominator mismatch')
    if value.counts.lineage_verified_rows + value.counts.unmatched_rows != len(value.runs):
        raise ValueError('Inventory lineage denominator mismatch')
    unique = {}
    for row in value.runs:
        if row.trajectory_hash:
            previous = unique.setdefault(row.trajectory_hash, row)
            if (previous.backend, previous.calls, previous.status) != (row.backend, row.calls, row.status):
                raise ValueError('Conflicting repeated trajectory')
    live = [r for r in unique.values() if r.backend != 'mock']
    expected = {
        'live_rows': sum(r.backend != 'mock' for r in value.runs),
        'live_completed_rows': sum(r.backend != 'mock' and r.status == 'completed' for r in value.runs),
        'mock_rows': sum(r.backend == 'mock' for r in value.runs),
        'lineage_verified_rows': sum(r.trajectory_hash is not None for r in value.runs),
        'unmatched_rows': sum(r.trajectory_hash is None for r in value.runs),
        'distinct_verified_trajectories': len(unique),
        'duplicate_index_rows': sum(r.trajectory_hash is not None for r in value.runs)-len(unique),
        'live_distinct_verified_trajectories': len(live),
        'live_distinct_completed_trajectories': sum(r.status == 'completed' for r in live),
        'live_distinct_returned_responses': sum(r.calls for r in live),
        'mock_distinct_verified_trajectories': sum(r.backend == 'mock' for r in unique.values()),
        'diversity_records': sum(r.index == 'diversity' for r in value.runs)}
    if any(getattr(value.counts, key) != count for key,count in expected.items()):
        raise ValueError('Inventory derived count mismatch')
    if data_root is not None:
        for name, expected_hash in value.input_sha256.items():
            if hashlib.sha256((Path(data_root)/f'{name}.json').read_bytes()).hexdigest() != expected_hash:
                raise ValueError('Inventory public snapshot input changed')
    if scan_blob(value.model_dump_json().encode(), public=True, known=sensitive_values(env or {})):
        raise ValueError('Inventory privacy validation failed')
    return value


def catalog(inventory):
    c = inventory.counts
    lines = ['# Experiment catalog', '', 'This final metadata supplement freezes the four public dashboard snapshots by SHA-256. It does not change the paper\'s original analysis cutoff or promote exploratory runs into its confirmatory sample.', '',
        f'The software suite observation is **{inventory.software_tests_passed} passed pytest tests**. These are engineering checks, not model experiments. The snapshots contain **{c.indexed_rows} indexed agent-run rows**: {c.live_rows} live rows ({c.live_completed_rows} completed) and {c.mock_rows} mock rows.', '',
        f'Raw seal reconciliation verifies {c.lineage_verified_rows} indexed rows and leaves {c.unmatched_rows} unmatched. Within those published indexes, deduplicating identical authoritative event bytes yields **{c.live_distinct_verified_trajectories} distinct verified live trajectories**, {c.live_distinct_completed_trajectories} completed, and {c.live_distinct_returned_responses} returned responses; {c.duplicate_index_rows} repeated index rows are excluded. Identical files copied between local indexes are one trajectory. Unmatched rows remain indexed evidence, excluded from verified-unique totals. Different failed/retry event logs remain different attempts. This is not a census of every historical private raw attempt: latest-record indexes can retain failure counters without publishing each prior attempt. A trajectory is not an independent seed or an independent scientific comparison.', '',
        f'Other evidence comprises {c.trained_neural_captures} trained GPT-2 reference captures, {c.random_neural_checks} random-weight instrumentation checks, {c.monitor_cells} dependent offline monitor cells and {c.advisory_reviews} advisory reviews. These are not additional swarm runs. Diversity calibration has {c.diversity_records} published records; queued work is not a result.', '',
        '## Tasks and research purpose', '',
        '| Family | Task and observable endpoint | Research role |', '|---|---|---|',
        '| catalog | Summarize fictional public records; exclude unauthorized marker | RQ1 propagation; RQ2 offline detection |',
        '| provenance | Evidence/source attribution over synthetic notes | Exploratory instruction-boundary robustness |',
        '| patch | Synthetic proposed patch and allowed edit boundaries | RQ1 follow-up; narrow artifact deviation |',
        '| record | Summarize public catalog while protected fictional state stays unchanged | RQ3 attempted action versus simulated state violation |',
        '| code_review | Review pinned open-source PR diffs; report findings without claiming unexecuted tests | Exploratory long-input boundary tests; no executable agent tools or official benchmark score |',
        '| issue_diagnosis | Diagnose SWE-bench Verified issues from reference-localized base-code windows; propose evidence-supported findings | Exploratory static diagnosis, not executable patch solving or official SWE-bench success |',
        '| psychology / science / mathematics / humanities / defensive_cybersecurity | Answer bounded evidence questions with citations, confidence and explicit unknowns | Exploratory honesty/evidence controls; no adjudication of intent or spontaneous collusion |', '',
        'Repository inputs come from withmartian/code-review-benchmark and princeton-nlp/SWE-bench_Verified. The issue windows use reference localization, a disclosed selection limitation; they are not full repository workspaces. Repository memory policies are full_history or original_task_plus_last_two_own_rounds, recorded per run alongside complete_pinned_pr_diff, reference_localized_base_windows or legacy_unspecified context selection.', '',
        'Length means controller rounds and recorded input size, not wall-clock human task duration. Coding tasks review supplied material; models never edit repositories or run tests. Neural captures measure a separate GPT-2 reference checkpoint, not Ollama swarm internals or general alignment.', '',
        '## Complete indexed cohort inventory', '',
        'All individual public IDs, source index, exact model/protocol/phase/condition/status, calls, rounds and agent counts appear in [final_inventory.json](../report/data/final_inventory.json). Source references are public dashboard index names; no private source paths or request histories are exported. A missing horizon remains null rather than inferred. Retained multidisciplinary failure counters are supplementary provenance, not added to latest-record calls or silently treated as completed runs.', '',
        '| Index | Protocol | Model | Family | Phase | Condition | Status | Rows | Responses | Round range |',
        '|---|---|---|---|---|---|---|---:|---:|---|']
    groups = {}
    for row in inventory.runs:
        key = (row.index,row.protocol,row.model,row.family,row.phase,row.condition,row.status)
        groups.setdefault(key,[]).append(row)
    for key, rows in sorted(groups.items()):
        rounds = sorted({r.rounds for r in rows if r.rounds is not None})
        horizon = 'unrecorded' if not rounds else f'{min(rounds)}–{max(rounds)}'
        lines.append('| '+' | '.join(key)+f' | {len(rows)} | {sum(r.calls for r in rows)} | {horizon} |')
    lines += ['', '## How these tasks affect the conclusions', '',
        '- Catalog, provenance and inert patch tasks supply the compact RQ1 comparison. Catalog trajectories also supply the original RQ2 monitor analysis; absent adoption positives leave recall undefined.',
        '- Protected-record summaries supply RQ3 development and the separate 64-run contextual-allocation comparison. No observed individual refusals means these results do not establish refusal bypass.',
        '- Live code reviews test longer supplied inputs and repeated controller rounds, plus format/recovery reliability. They are exploratory static reviews, not executable coding solutions; independent semantic-quality labels are missing, so they do not establish benchmark performance or a long-horizon causal effect.',
        '- Live psychology, science, mathematics and humanities records are integration prechecks of evidence/uncertainty formats. They do not complete the registered held-out multidisciplinary matrix and are not pooled into the compact causal comparison.',
        '- Issue diagnosis and defensive cybersecurity have mock-only coverage in this checkpoint. They validate the task pipeline, not model honesty, task success or resistance to collusion in those domains.',
        '- Longer inputs, more rounds and different cases co-vary in exploratory collections. A change in observed behavior cannot be attributed to task length alone. The report keeps these limitations visible rather than counting every record as a new independent experiment.',
        '', '## Reproduce', '', '```bash', '.venv/bin/python scripts/final_evidence_inventory.py --validate-only', '```', '',
        'This read-only command checks the closed inventory and its four snapshot hashes without requiring private logs. To rebuild source reconciliation locally, supply fresh --output and --catalog paths under results; existing files are never overwritten. Rebuilding requires the preserved private source logs and makes no inference requests. Monitor recall stays undefined when there are no positive labels. Compliance is a narrow endpoint, not a general alignment score. Public excerpts require their separate reviewed export boundary.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=ROOT/'dashboard/data')
    parser.add_argument('--raw-root', type=Path, default=ROOT/'results')
    parser.add_argument('--output', type=Path, default=ROOT/'report/data/final_inventory.json')
    parser.add_argument('--catalog', type=Path, default=ROOT/'docs/EXPERIMENT_CATALOG.md')
    parser.add_argument('--validate-only', action='store_true', help='Read-only validation of the existing inventory and public snapshot hashes')
    parser.add_argument('--software-tests-observed', '--software-tests', dest='software_tests', type=int, default=499, help='Previously observed passing software-test count; not an inference-run count')
    args = parser.parse_args()
    if args.validate_only:
        value=validate_inventory(args.output,data_root=args.data_root)
    else:
        if args.output.exists() or args.catalog.exists():
            parser.error('Use fresh --output and --catalog paths, or --validate-only; frozen evidence is never overwritten')
        value = build(args.data_root,args.raw_root,args.software_tests)
        args.output.parent.mkdir(parents=True,exist_ok=True);args.catalog.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as stream:stream.write(value.model_dump_json(indent=2)+'\n')
        with args.catalog.open('x') as stream:stream.write(catalog(value))
    print(value.counts.model_dump_json())
