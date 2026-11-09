# Reviewed static dashboard publication

The dashboard has two distinct delivery modes. The local service indexes sealed logs and exposes private controller progress and bounded redacted trace routes on loopback. GitHub Pages serves only a reviewed static snapshot. A browser refresh on Pages cannot contact private inference servers or import newly completed logs by itself.

## Prepare a reviewable artifact

Checkpoint the sanitized local cache separately from collection, then build a fresh publication directory:

```bash
.venv/bin/python scripts/export_live_dashboard.py
.venv/bin/python scripts/publication_readiness.py \
  --source dashboard --artifact site-dist/review-FRESH --build \
  --out results/publication-readiness-FRESH.private.json
```

Use fresh output paths. The readiness report stays outside the publication artifact. It records file hashes, source-index timestamps/ages, separate live/mock inventory, workflow checks and remaining operator gates. An old reviewed checkpoint can be valid reproducibility evidence; its age must not be presented as live collection.

The existing builder copies only explicit HTML/CSS/JavaScript, validated public indexes, approved sanitized trace files and an empty `.nojekyll`. Unknown source files are ignored. The readiness inspector rejects extra or modified artifact files, generated-marker content, symlinks, duplicate HTML identifiers, unlabeled select controls, incomplete navigation and asset paths that break under a GitHub project prefix. Every copied data index is revalidated against its closed schema and publication privacy policy.

These checks do not prove semantic task quality, reviewer accuracy, general alignment or complete accessibility. Browser layout/responsive review remains a separate check. No browser was installed or remote service changed for this preparation.

## GitHub workflow and release gates

The current `.github/workflows/pages.yml` runs security/reproducibility checks for pull requests. Artifact upload and Pages deployment require `main` and a push or explicit workflow dispatch; deployment depends on successful checks. Actions are pinned and Pages write/OIDC permissions are scoped to the deploy job. A draft implementation PR is not automatically merged or deployed by this checker.

Main-only workflow conditions do not prove a human reviewed the revision. Configure appropriate branch protection and the `github-pages` environment in GitHub before an authorized release. Review optional trace text, numerical exclusions, benchmark-adaptation limitations and the exact code/data revision first.

At the last authenticated operator check, this repository was private and Pages was not enabled. This tool does not change visibility, enable Pages or claim a public URL. Select a reviewed public-release approach separately, enable GitHub Actions as the Pages source if desired, and verify the returned deployment URL after authorization. Keep raw traces, environment files, upstream code/reference material, human-review exports and hardware telemetry out of the artifact.

Public links and a demo are optional for the hackathon. Final PDF/template review, authorship declarations and actual submission through the organizer form remain the author's actions. A built artifact, passing CI or generated PDF is not a submission confirmation.
