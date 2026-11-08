"""Reproducible cohort-separated figures from validated research snapshots."""
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path

from .evidence_stats import cohort_key, neural_diagnostics, paired_effects, summaries, wilson
from .research_publication import validate_research_snapshot


def generate_report(snapshot_path, output, max_cohort_figures=16, legacy_path=None):
    import os
    from collections import defaultdict
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(output / '.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    snapshot = validate_research_snapshot(snapshot_path)
    rows = [r.model_dump() for r in snapshot.studies]
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate run IDs in report source')
    if max_cohort_figures < 0:
        raise ValueError('Invalid figure cap')
    try:
        import seaborn as sns
        sns.set_theme(style='whitegrid', context='paper')
    except ImportError:
        pass
    figures = []
    def table(name, records):
        if not records:
            (output / name).write_text('')
            return
        with (output / name).open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    def save(fig, name, caption):
        fig.tight_layout()
        fig.savefig(output / f'{name}.png', dpi=180)
        fig.savefig(output / f'{name}.svg')
        plt.close(fig)
        figures.append({'name': name, 'caption': caption})
    groups = defaultdict(list)
    for row in rows:
        groups[cohort_key(row)].append(row)
    summary = summaries(rows)
    pairs = paired_effects(rows)
    neural = [neural_diagnostics(r.model_dump()) for r in snapshot.neural]
    table('runs.csv', rows)
    table('cohort_summary.csv', summary)
    table('paired_effects.csv', pairs)
    table('neural_quality.csv', neural)
    table('monitor_summary.csv', [r.model_dump() for r in snapshot.monitor])
    table('review_queue.csv', [r.model_dump() for r in snapshot.reviews])
    for index, (key, selected) in enumerate(sorted(groups.items(), key=lambda x: (x[0][1]=='mock',str(x[0])))):
        if index >= max_cohort_figures:
            break
        stats = [r for r in summary if cohort_key(r) == key]
        fig, axes = plt.subplots(1, 3, figsize=(12, 3.7))
        labels = []
        for x, stat in enumerate(stats):
            labels.append(f'{stat["topology"]}/{stat["agent_count"]}\n{stat["intervention"]}')
            color = '#2878bd' if stat['intervention'] == 'none' else '#d45536'
            if stat['violation_rate'] is not None:
                rate = stat['violation_rate']
                low, high = stat['wilson95_working_model']
                axes[0].errorbar(x, rate, yerr=[[max(0, rate-low)], [max(0, high-rate)]], fmt='o', color=color, capsize=3)
            axes[0].text(x, 1.04, f'n={stat["scorable_runs"]}\n?={stat["indeterminate_or_unfinished"]}', ha='center', fontsize=6)
            matching = [r for r in selected if r['topology'] == stat['topology'] and
                        r['agent_count'] == stat['agent_count'] and r['intervention'] == stat['intervention']]
            values = [r['task_success_rate'] for r in matching if r['status'] == 'completed' and r['task_success_rate'] is not None]
            axes[1].scatter([x]*len(values), values, color=color, s=15, alpha=.6)
            for row in matching:
                axes[2].scatter(x, row['runtime'], color=color, marker='o' if row['status']=='completed' else 'x', s=18)
        for ax in axes:
            ax.set_xticks(range(len(labels)), labels, rotation=40, ha='right', fontsize=6)
        axes[0].set(title='Any objective violation / scorable run', ylim=(-.05, 1.2))
        axes[1].set(title='Task success / completed run', ylim=(-.05, 1.05))
        axes[2].set(title='All-attempt runtime; × = incomplete', ylabel='Seconds')
        first = selected[0]
        fig.suptitle(f'{first["model"]} · {first["backend"]} · protocol {first["protocol"]} · {first["task_family"]} / {first["split"]}\n'
                     f'{first["worker_label"]} · freeze {first["freeze_hash"][:12]} · {first["executor"]}', fontsize=9)
        save(fig, f'cohort-{index:03}', 'One frozen model/backend/digest/worker/protocol/task/split/executor cohort. '
             'Binomial 95% working-model intervals assume independent runs; synthetic variants may violate that assumption. '
             '? counts indeterminate/unfinished attempts. Violation is the objective run flag, not RQ1 downstream adoption. '
             'Task success includes invalid artifacts as failures; runtime includes failed attempts. No general alignment score.')
    monitor_groups = defaultdict(list)
    for row in snapshot.monitor:
        monitor_groups[(row.model, row.backend, row.protocol, row.cohort, row.topology, row.policy, row.monitor_seed)].append(row)
    for index, (key, selected) in enumerate(sorted(monitor_groups.items(), key=lambda x: str(x[0]))):
        if index >= max_cohort_figures:
            break
        fig, axes = plt.subplots(1, 2, figsize=(9, 3.5))
        for ax, metric in zip(axes, ['recall', 'false_positive_rate']):
            for row in selected:
                value = getattr(row, metric)
                if value is not None:
                    ax.scatter(row.visibility, value, color='#2878bd')
                    denom = row.tp + row.fn if metric == 'recall' else row.fp + row.tn
                    ax.annotate(f'n={denom}', (row.visibility, value), fontsize=7)
            if all(getattr(r, metric) is None for r in selected):
                ax.text(.5, .5, 'Undefined: zero denominator', ha='center', transform=ax.transAxes)
            ax.set(xlabel='Visibility', ylabel=metric, ylim=(-.05, 1.05))
        fig.suptitle(f'{key[0]} · {key[4]} · {key[5]} · mask seed {key[6]} · cohort {key[3]}', fontsize=8)
        save(fig, f'monitor-{index:03}', 'Matched monitor projections are dependent. Denominators label positives/negatives. '
             'Undefined recall is not zero. Do not pool policies or cohorts; monitor coverage is catalog-only.')
    for index, capture in enumerate(snapshot.neural):
        quality = neural[index]
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
        p = capture.patch
        names = ['clean', 'corrupt', 'patched', 'no-op', 'position control']
        values = [p.clean_target_logit, p.corrupt_target_logit, p.patched_target_logit, p.noop_target_logit, p.position_control_logit]
        axes[0].bar(names, values, color=['#2878bd','#d45536','#6d58c7','#78909c','#c28d26'])
        axes[0].tick_params(axis='x', rotation=25)
        axes[0].set(ylabel='Target-token logit', title='Measured intervention + controls')
        for layer in capture.layers:
            axes[1].plot(range(len(layer.clean_residual_rms)), layer.clean_residual_rms, label=f'L{layer.layer} clean')
            axes[1].plot(range(len(layer.corrupt_residual_rms)), layer.corrupt_residual_rms, linestyle='--', label=f'L{layer.layer} corrupt')
        axes[1].set(xlabel='Token position (contexts may differ)', ylabel='Residual RMS', title='Activation magnitude; not intent')
        axes[1].legend(fontsize=6)
        fig.suptitle(f'{capture.model} · {capture.evidence_type}', fontsize=9)
        save(fig, f'neural-{index:03}', f'Measured capture {capture.id}; no-op pass={quality["noop_pass"]}; '
             f'usable clean/corrupt gap={quality["baseline_gap_usable"]}. '
             'Random-weight captures are instrumentation only. RMS is not a named feature; unequal positions are not automatically aligned.')
    legacy_stats=[]
    if legacy_path:
        from .publication import validate_snapshot
        legacy=validate_snapshot(legacy_path)
        legacy_groups=defaultdict(list)
        for run in legacy.runs:legacy_groups[(run.cohort,run.topology,run.intervention)].append(run)
        for (cohort,graph,condition),attempts in sorted(legacy_groups.items()):
            valid=[r for r in attempts if r.status=='completed' and not r.parse_failures]
            count=sum(r.downstream_adoption_rate>0 for r in valid)
            legacy_stats.append({'cohort':cohort,'model':attempts[0].model,'backend':attempts[0].backend,
                'topology':graph,'intervention':condition,'attempts':len(attempts),'scorable_runs':len(valid),
                'any_downstream_adoption_runs':count,'wilson95_working_model':wilson(count,len(valid)),
                'mean_downstream_adoption':sum(r.downstream_adoption_rate for r in valid)/len(valid) if valid else None,
                'mean_messages_delivered':sum(r.messages_delivered for r in attempts)/len(attempts)})
        table('legacy_summary.csv',legacy_stats)
        for index,cohort in enumerate(sorted({r.cohort for r in legacy.runs})):
            selected=[r for r in legacy.runs if r.cohort==cohort]
            fig,axes=plt.subplots(1,2,figsize=(9,3.5))
            labels=[]
            for x,stat in enumerate([r for r in legacy_stats if r['cohort']==cohort]):
                labels.append(stat['topology']+' / '+stat['intervention'])
                valid=[r for r in selected if r.topology==stat['topology'] and r.intervention==stat['intervention'] and r.status=='completed' and not r.parse_failures]
                axes[0].scatter([x+(j-(len(valid)-1)/2)*.07 for j in range(len(valid))],[r.downstream_adoption_rate for r in valid],color='#2878bd',s=15)
                axes[0].text(x,1.01,f'n={len(valid)}',ha='center',fontsize=7)
                axes[1].bar(x,stat['mean_messages_delivered'],color='#6977bf')
            for ax in axes:ax.set_xticks(range(len(labels)),labels,rotation=40,ha='right',fontsize=6)
            axes[0].set(ylabel='Downstream adoption fraction',ylim=(-.05,1.05))
            axes[1].set(ylabel='Delivered messages / run')
            fig.suptitle(selected[0].model+' · '+selected[0].backend+' · frozen legacy cohort',fontsize=9)
            save(fig,f'legacy-{index:03}','Original RQ1 downstream artifact outcomes and exposure. Agents are nested; paired seeds are dependent. Zero events do not imply zero underlying risk; see working-model intervals in legacy_summary.csv.')
    provenance = {'snapshot_sha256': hashlib.sha256(Path(snapshot_path).read_bytes()).hexdigest(),
                  'analysis_source_sha256': hashlib.sha256(Path(__file__).read_bytes() +
                      Path(__file__).with_name('evidence_stats.py').read_bytes()).hexdigest(),
                  'snapshot_generated_utc': snapshot.generated_utc,
                  'legacy_snapshot_sha256': hashlib.sha256(Path(legacy_path).read_bytes()).hexdigest() if legacy_path else None,
                  'matplotlib': importlib.metadata.version('matplotlib')}
    evidence = {'provenance': provenance, 'cohort_summaries': summary, 'legacy_summaries':legacy_stats, 'paired_effects': pairs,
                'neural_quality': neural, 'omitted_cohort_figures': max(0, len(groups)-max_cohort_figures),
                'omitted_monitor_figures': max(0, len(monitor_groups)-max_cohort_figures),
                'limitations': ['Run unit; agents are nested, conditions paired, variants template-dependent.',
                    'Wilson intervals are working-model descriptions, not cluster-adjusted population inference.',
                    'Matched comparisons reject duplicate attempts; missing/invalid pairs remain counted.',
                    'Different freezes are never implicitly pooled. This may split otherwise comparable runs.',
                    'Snapshot objective flags do not replace raw downstream adoption/exposure/round trajectories.',
                    'No trained-checkpoint or SAE evidence exists merely because tooling is installed.']}
    (output / 'evidence.json').write_text(json.dumps(evidence, indent=2)+'\n')
    text = ['# Contagion research evidence report', '', f'Snapshot: {snapshot.generated_utc}',
            f'{len(rows)} attempts; {len(groups)} strict frozen cohorts; {len(snapshot.neural)} measured neural captures.',
            'Tables include every cohort; figure caps and omissions are recorded in evidence.json.', '',
            '## Interpretation limits', *['- '+s for s in evidence['limitations']], '',
            '## Reproduction', 'Input and analysis hashes are in evidence.json. Raw logs remain authoritative.',
            'Tables: runs.csv, cohort_summary.csv, paired_effects.csv, neural_quality.csv.', '']
    for figure in figures:
        text.extend([f'## {figure["name"]}', figure['caption'], f'![{figure["name"]}]({figure["name"]}.png)', ''])
    (output / 'report.md').write_text('\n'.join(text))
    (output / 'figure_catalog.json').write_text(json.dumps(figures, indent=2)+'\n')
    return {'runs': len(rows), 'figures': len(figures), 'cohorts': len(groups)}
