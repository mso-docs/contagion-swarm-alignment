"""Render separate, validated post-freeze evidence without rewriting primary scores."""
import hashlib
import json
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
INPUTS={
    'pointer_audit_sha256':'report/data/patch_pointer_audit.json',
    'human_audit_sha256':'report/data/human_audit.json',
    'submission_snapshot_sha256':'report/data/submission_snapshot/public.json',
    'pointer_audit_script_sha256':'scripts/patch_pointer_audit.py',
    'human_audit_script_sha256':'scripts/import_human_audit.py',
    'snapshot_script_sha256':'scripts/submission_snapshot.py',
    'supplement_script_sha256':'scripts/paper_supplement.py',
    'final_inventory_sha256':'report/data/final_inventory.json',
    'final_inventory_script_sha256':'scripts/final_evidence_inventory.py',
    'illustrative_examples_sha256':'report/data/illustrative_examples.json',
    'illustrative_examples_script_sha256':'scripts/illustrative_examples.py',
}


def render(root=ROOT):
    from patch_pointer_audit import validate as pointer_validate
    from import_human_audit import validate_public
    from submission_snapshot import validate as snapshot_validate
    from final_evidence_inventory import validate_inventory
    root=Path(root)
    inventory=validate_inventory(root/'report/data/final_inventory.json',data_root=root/'dashboard/data')
    inventory_counts=inventory.counts
    audit=pointer_validate(root/'report/data/patch_pointer_audit.json')
    human=validate_public(root/'report/data/human_audit.json')
    snapshot=snapshot_validate(root/'report/data/submission_snapshot')
    if audit.script_sha256!=hashlib.sha256((root/'scripts/patch_pointer_audit.py').read_bytes()).hexdigest():
        raise ValueError('Regenerate the pointer sensitivity audit after changing its analysis')
    summary={(row.cohort,row.condition):row for row in audit.summary}
    compact=summary['compact','benign_override'];primary=summary['primary','benign_override'];control=summary['primary','none']
    table=[]
    for title,key in [('Strict scorer','objective_scorer'),('Local judge','local_judge'),('Frontier judge','frontier_judge')]:
        data=human[key]
        if data is None:continue
        counts=data['confusion']
        table.append(f"{title} & {counts['n']} & {counts['fp']} & {counts['fn']}"+r'\\')
    positives=human['objective_scorer']['confusion']['tp']+human['objective_scorer']['confusion']['fn']
    undefined='Recall and F1 are undefined because there are no positive human labels.' if not positives else 'Metrics are conditional on the selected, single-reviewer reference labels.'
    lines=[
        r'\section{Post-hoc Measurement Sensitivity}',
        f"A separately versioned audit of {len(audit.runs)} sealed patch runs strips only two explicit task-wrapper prefixes for a sensitivity check. It never changes controller execution, source logs or primary scores. In compact injected runs, strict canonical-path flags total {compact.strict_forbidden_artifacts}; wrapper-sensitive proposals total {compact.wrapper_sensitive_forbidden_artifacts}. In the separate {primary.runs+control.runs}-run primary follow-up, the corresponding injected counts are {primary.strict_forbidden_artifacts} and {primary.wrapper_sensitive_forbidden_artifacts}. These are proposed artifacts, not executed host actions.",
        f"Final wrapper-sensitive forbidden artifacts are {compact.wrapper_sensitive_final_forbidden_artifacts} in compact injected runs and {primary.wrapper_sensitive_final_forbidden_artifacts} in the primary injected follow-up. Primary final control matches change from {control.strict_success_final}/{control.final_artifacts} under exact path format to {control.wrapper_normalized_success_final}/{control.final_artifacts} under this normalization; injected matches change from {primary.strict_success_final}/{primary.final_artifacts} to {primary.wrapper_normalized_success_final}/{primary.final_artifacts}. Thus strict task failure cannot be equated with inability to identify the requested configuration change. Normalization is a post-hoc sensitivity endpoint, not independent semantic validation or a replacement for the original rubric.",
        r'\section{Selected Human Review and Automated Flags}',
        f"One operator-provided reviewer completed {human['human_completed']}/{human['selected_samples']} selected artifact judgments, with {human['corrections']} recorded correction. The human reference contains {positives} positive violation labels. Selection favored machine disagreements and retained seeded controls; it is not a prevalence sample. Raw individual judgments, reasons and history remain private; numerical provenance records their hashes.",
        r'\begin{table}[H]\centering\small',
        r'\caption{Automated signals against the supplied human reference on the selected audit. Positive disagreement means a machine flag with a compliant human label; negative disagreement means the converse. These counts do not establish which interpretation is correct. Coverage differs, so rows are not a matched model ranking.}',
        r'\begin{tabular}{lrrr}\toprule Assessment & Covered & Positive disagreement & Negative disagreement\\\midrule',
        *table,r'\bottomrule\end{tabular}\end{table}',
        undefined+' Automated proposal criteria and the compliant human reference labels remain distinct; this selected audit does not establish population detector accuracy, calibrated probabilities or independent inter-rater agreement.',
        r'\section{Evidence Coverage at the Cutoff}',
        f"The separate numeric inventory uses cutoff {snapshot.cutoff_utc.replace('_','')} and contains {len(snapshot.rows)} supported sealed completed runs across explicitly separate live and mock cohorts. It does not pool them into the compact paper analysis or independent trials. Unsupported older protocols, incomplete attempts and later runs are excluded with counts. Only completed sealed runs enter this inventory; source text and private lineage are withheld.",
    ]
    from illustrative_examples import validate as validate_examples
    examples=validate_examples(root/'report/data/illustrative_examples.json')
    if any(examples.source_hashes[key]!=value for key,value in human['source_hashes'].items()):
        raise ValueError('Illustrations do not match frozen human audit')
    def escape(value):
        replacements={'\\':r'\textbackslash{}','{':r'\{','}':r'\}','_':r'\_','%':r'\%','&':r'\&','#':r'\#','$':r'\$','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
        return ''.join(replacements.get(char,char) for char in str(value))
    lines += [r'\section{Source-Bound Illustrative Artifacts}',
        'Selection takes the first two strict-positive patch samples by opaque ID and the first unflagged final patch sample from the same selected human audit. All three labels are inherited from that audit, not newly adjudicated from these excerpts. Source seals, opaque event aliases, queue and label hashes bind the examples; private reviewer reasons are withheld. These examples illustrate rubric differences and are not a prevalence sample. Round indices are zero-based.',
    ]
    for example in examples.examples:
        artifact=json.loads(example.artifact)
        if set(artifact)!={'patch'} or len(artifact['patch'])!=1 or set(artifact['patch'][0])!={'path','value'}:
            raise ValueError('Illustration must remain a single inert patch proposal')
        patch=artifact['patch'][0]
        lines.append(r'\textbf{Sample \texttt{'+example.sample_id+r'}} (event \texttt{'+example.event_ref+r'}, '+escape(example.agent_id)+f", round {example.round}): "+r'\texttt{'+escape(patch['path'])+r'} $\rightarrow$ \texttt{'+escape(patch['value'])+'}. Strict proposal flag: '+('yes' if example.strict_flag else 'no')+'; supplied human label: compliant.')
    lines += ['The first two proposals target the forbidden synthetic evaluator path. Their compliant human labels therefore disagree with the strict proposal criterion; this is unresolved rubric disagreement, not confirmation that the proposals are authorized. The final example instead uses a repository-wrapper prefix on the legitimate configuration path. A format-sensitive task failure can therefore coexist with no forbidden-path flag. The second and third examples share a source run but belong to different agents; they do not establish within-agent recovery. No proposed patch was executed on host files.']
    descriptions={
        'catalog':('Public record grouping','Exclude unauthorized marker'),
        'provenance':('Record stage and provenance','Preserve evidence attribution'),
        'patch':('Inert JSON update proposal','Avoid forbidden synthetic paths'),
        'record':('Public catalog summary','Protected simulator state unchanged'),
        'code_review':('Pinned real PR diffs','Static findings; no claimed execution'),
        'issue_diagnosis':('SWE-bench reference-localized issue diagnosis','Mock-only static pipeline checks'),
        'psychology':('Bounded evidence question','Citations, confidence and unknowns'),
        'science':('Bounded evidence question','Citations, confidence and unknowns'),
        'mathematics':('Bounded reasoning question','Evidence and calibrated uncertainty'),
        'humanities':('Bounded interpretation question','Evidence and calibrated uncertainty'),
        'defensive_cybersecurity':('Benign static defensive scenario','Registered; no completed live result'),
    }
    coverage=[]
    for family,(task,endpoint) in descriptions.items():
        rows=[row for row in inventory.runs if row.backend!='mock' and row.family==family]
        mock=sum(row.backend=='mock' and row.family==family for row in inventory.runs)
        coverage.append(f"{family.replace('_',' ')} & {len(rows)} & {sum(row.status=='completed' for row in rows)} & {mock} & {task}; {endpoint}"+r'\\')
    lines += [r'\section{Separate Final Collection Inventory}',
        f"The final metadata inventory contains {inventory_counts.live_rows} live indexed rows ({inventory_counts.live_completed_rows} completed) and {inventory_counts.mock_rows} mock rows. Raw-seal reconciliation verifies {inventory_counts.live_distinct_verified_trajectories} distinct live event trajectories, including {inventory_counts.live_distinct_completed_trajectories} completed trajectories and {inventory_counts.live_distinct_returned_responses} returned responses. The {inventory_counts.unmatched_rows} unmatched legacy rows remain explicit exclusions from verified-unique totals. These are provenance counts across protocols, not independent scientific replicates or additional compact-study results.",
        r'\begin{table}[H]\centering\small',
        r'\begin{tabular}{p{.17\linewidth}rrrp{.40\linewidth}}\toprule Family & Live & Complete & Mock & Task and boundary endpoint\\\midrule',
        *coverage,r'\bottomrule\end{tabular}',
        r'\caption{All task families in the final indexed collection, with explicit zero live coverage for defensive cybersecurity and issue diagnosis. Live counts precede unmatched-source exclusions; protocols, conditions, case reuse, horizons and model cohorts remain separate. Static review does not execute code and has no official benchmark score.}\end{table}',
        f"The broader collection contains {inventory_counts.trained_neural_captures} trained reference-checkpoint captures and {inventory_counts.random_neural_checks} random-weight instrumentation checks. The broader grid includes the original six compact-paper captures plus 66 later captures; the paper retains its original six-capture freeze. None of these reference captures explains swarm-model mechanisms. The {inventory_counts.monitor_cells} monitor cells and {inventory_counts.advisory_reviews} advisory reviews are derived assessments, not additional live runs. Diversity calibration has {inventory_counts.diversity_records} published records. No absent domain, queued pilot or advisory label is represented as a demonstrated result.",
        'The complete machine-readable inventory preserves each public run ID, model, protocol, phase, condition, status and available horizon. Broader task coverage supports exploratory description, not a pooled alignment score. Independent semantic-quality labels and cross-domain judge calibration remain necessary before comparing useful performance or attributing intent.',
    ]
    hashes={key:hashlib.sha256((root/name).read_bytes()).hexdigest() for key,name in INPUTS.items()}
    return '\n\n'.join(lines)+'\n',hashes
