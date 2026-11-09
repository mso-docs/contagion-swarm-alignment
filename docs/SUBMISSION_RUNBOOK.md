# Final submission runbook

[Documentation home](README.md) · [Developer guide](DEVELOPMENT.md)


Collection and submission are separate. A dashboard can keep receiving sealed runs while the
paper and its supplemental snapshot remain fixed. Do not replace the compact paper's evidence
with a moving export.

1. Freeze an explicit evidence cutoff using [SUBMISSION_SNAPSHOT.md](SUBMISSION_SNAPSHOT.md).
   Keep only its three validated public files in reviewer-facing packages; private lineage stays
   local.
2. Import the actual human CSV and correction history, then run [the
   rehearsal](SUBMISSION_REHEARSAL.md). Report the selected subset's denominators and the
   frontier judge's covered intersection. AI judgments never supply missing human labels.
3. Rebuild the notebook and PDF, then inspect figures, citations, methods and limitations. The
   supplementary [RQ assessment](RQ_ASSESSMENT.md) separates completed comparisons from pending
   claims.

```bash
.venv/bin/python scripts/build_paper.py --out results/paper-draft
.venv/bin/python scripts/submission_audit.py \
  --paper-dir results/paper-draft --out results/submission-audit-FRESH.private.json
.venv/bin/python scripts/research_bundle.py \
  --out results/research-bundle-FRESH \
  --paper-dir results/paper-draft \
  --snapshot results/submission-snapshot-FRESH
```

The build creates an actual PDF, executed notebook, figure exports and input/build hashes. The
bundle runs an offline source-copy figure reproduction check. Use fresh snapshot, audit and
bundle paths; preserve previous receipts. The bundle is not a submission confirmation.

4. Compare the exact PDF against the current official template. Record author review against its
   PDF hash and exact code revision using the rehearsal's attestation schema. Rebuilding either
   invalidates the old review record.
5. Verify access as an unauthenticated reviewer. The project repository is currently private and
   Pages is not enabled; a local dashboard or authenticated GitHub link is not a public
   artifact. Share the scrubbed allowlisted bundle through an organizer-supported method, or
   arrange a separately reviewed public release. Do not change repository visibility or publish
   private traces to fix a link.
6. Submit the exact reviewed PDF through the official form. Complete team, track and contact
   fields yourself; keep contact details and the organizer receipt private. Confirm the uploaded
   PDF hash/version and retain the confirmation.

The official repository and video links are optional. An inaccessible optional code link does
not justify claiming public reproducibility. Final PDF submission, authorship declarations and
publication preferences require the author's action.

## Evidence to emphasize
- Compact RQ1: intermediate direct-exposure deviations and zero final downstream violations are
  distinct outcomes.
- RQ2: undefined recall without adoption positives is a measurement limit, not detector success.
- RQ3: contextual allocation is distinct from the separately registered decomposition pilot; no
  refusal-bypass conclusion without individual refusals and verified collective behavior.
- Safeguards: compare boundary outcomes and legitimate semantic utility only when both are
  available. Missing quality stays undefined.
- Interpretability: trained GPT-2 reference captures are separate from Ollama swarm internals.

See [the optional demo outline](SUBMISSION_DEMO.md) for a concise walkthrough. Keep the laptop
and authorized inference tunnels connected if background collection should continue; registered
limits and error stops still apply.
