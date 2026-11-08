"""Render separate, validated post-freeze evidence without rewriting primary scores."""
import hashlib
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
}


def render(root=ROOT):
    from patch_pointer_audit import validate as pointer_validate
    from import_human_audit import validate_public
    from submission_snapshot import validate as snapshot_validate
    root=Path(root)
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
    hashes={key:hashlib.sha256((root/name).read_bytes()).hexdigest() for key,name in INPUTS.items()}
    return '\n\n'.join(lines)+'\n',hashes
