# Human audit and submission rehearsal

The rehearsal reads saved evidence and reports remaining gates. It never creates human judgments, uploads a PDF, merges code or confirms submission. Model labels remain advisory. The focused review queue is judge-informed and not population representative.

## Complete the focused audit

Open <http://127.0.0.1:8780/artifact-triage.html>. Review each sample against its displayed instruction and visible evidence. Choose a behavior and write a specific reason. Use `ambiguous` or `unscorable` when warranted; these require resolution before the fully adjudicated gate passes. The machine labels are withheld from this page.

Download both the labels CSV and correction history before closing. Keep both private under `results/reviews/`. The page holds work in memory and cannot save the CSV to the repository for you. Import the history to continue later. Preserve the original blank file; pass your downloaded CSV explicitly:

```bash
.venv/bin/python scripts/submission_rehearsal.py \
  --human results/reviews/my-human-labels.csv \
  --check-local --check-links \
  --out results/submission-rehearsal-after-review.private.json
```

Use a fresh output filename each time. With no `--human`, the tool reads the selected queue's `human_labels.csv`. `--second-human` accepts an independently completed second CSV. This can report agreement; AI reviews never count as independent human raters. CSV authorship remains an operator declaration, not something software can authenticate.

The report compares the objective scorer and both judges against **only saved human labels**. Frontier comparisons use its predeclared covered intersection; missing-by-design rows are not errors. Undefined recall stays null. Judge-informed audit metrics describe the selected subset, not overall judge accuracy or the prevalence of misalignment.

Validate matching CSV/history exports and preserve them in a fresh private directory:

```bash
.venv/bin/python scripts/import_human_audit.py \
  --human results/reviews/my-human-labels.csv \
  --history results/reviews/my-human-history.private.json \
  --out results/reviews/my-human-audit
```

The importer checks the exact blinded dataset hash, contiguous correction sequences, allowed decisions, sample IDs and latest-history/CSV agreement. It keeps private copies and receipts with restrictive permissions and never replaces an existing audit. Its numeric-only candidate excludes raw labels, reasons and paths. `validate_public(path)` checks the closed schema, source hashes, confusion denominators, coverage and rate mathematics without needing private files. Any scorer/human divergence marks calibration preliminary; reporting discordant flags is possible, but established false-positive or accuracy claims require further rubric analysis. Saved human rows stay unchanged. A completed audit can still contain honest disagreement with automated labels.

## Verified official requirements

Checked the current [Apart guidelines](https://apartresearch.com/sprints/swarm-alignment-2026) and [AIAF event page](https://www.aialignmentfoundation.org/hackathons/swarm-alignment-2026) on November8,2026. The global report requires the linked official template, PDF format, at most8 main pages excluding references/appendices, a150–250-word abstract, authors/affiliations and a limitations/dual-use/ethics appendix. The global deadline is November8 at23:59AoE, equivalent to November9 at06:59EST. Repository and3–5-minute demo links are optional. Submit through the official page; retain the confirmation and verify it identifies the correct PDF. A revised submission with the same title replaces the prior one before the deadline. The author remains responsible for report accuracy and must identify preexisting work. Global evaluation covers impact/innovation, execution and clarity; this tool assigns no competition score.

The Google template copy URL could not be opened by the web reader. The optional direct DOCX probe independently records its HTTP status/hash and compares it with `report/template_format.json`; retrieval or hash equality alone does not replace author visual comparison. A newly changed template remains an explicit review gate.

## Rehearse the exact artifact

```bash
.venv/bin/python scripts/submission_rehearsal.py \
  --check-links --check-local \
  --out results/submission-rehearsal-before-submit.private.json
```

No network calls occur unless the check flags are present. Public checks use a fixed allowlist: official guidelines, project repository, exact current commit, frozen numeric evidence at that commit, and the official DOCX export. Only the official template may follow up to three redirects, restricted to HTTPS Google-owned hosts. Other redirects are not followed. The private check reads only the fixed loopback review route and compares its body hash and security headers; its content is never included in the report. A network or stale-build failure is recorded as a remaining gate.

For final author review, create a private JSON file with this exact schema using the reviewed PDF SHA-256 and code revision reported by the rehearsal. Set a check to `true` only after completing it; no generated template is pre-approved:

```json
{
  "schema_version": "submission-author-attestation-1.0",
  "paper_sha256": "REPLACE_WITH_REVIEWED_PDF_SHA256",
  "code_revision": "REPLACE_WITH_EXACT_REVIEWED_COMMIT",
  "reviewed_utc": "REPLACE_WITH_ACTUAL_TIMEZONE_AWARE_REVIEW_TIME",
  "checks": {
    "claims_and_citations_reviewed": false,
    "official_template_compared": false,
    "public_revision_reviewed": false,
    "figures_reviewed": false
  }
}
```

Pass `--author-attestation results/reviews/author-attestation.private.json` on the final run. A rebuilt PDF or changed code revision invalidates the old attestation. This is a record of author review, not a cryptographic proof of review.

The final operator still needs to select publishing preference, tracks, team details and contact information in the official form. Do not commit personal contact fields. Upload the exact hashed PDF only after author review, then retain the organizer confirmation privately. A successful rehearsal is not submission confirmation.
