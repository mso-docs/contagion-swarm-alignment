# Reproducibility checklist

- [x] New source and task authored in this repository; no imported project implementation.
- [x] Configuration snapshots, protocol/source hashes, seed schedules and undirected graph edges.
- [x] Raw invocation/response traces, independent contexts, original/delivered intervention text.
- [x] Deterministic mock, ordered scheduler and reproducibility tests (excluding timing).
- [x] Exclusive attempts, completed-only resume, checksums, explicit failure/budget statuses.
- [x] Offline metrics/figures regenerated from raw events; manual artifact review export.
- [x] Python dependencies declared; local exact-version snapshot in requirements.lock.txt.
- [x] Operator configures endpoint and selects installed model tag/digest.
- [x] Successful logged live smoke request and output parsing.
- [x] One live paired pilot inspected; protocol/scorer frozen before batch.
- [x] Live 18-condition RQ1 matrix and failure accounting.
- [ ] Hardware details recorded by operator (manifest records controller OS/architecture only).
- [x] RQ2 implementation/leakage tests; separate RQ3 development simulator comparison.
- [ ] Strengthened follow-up live results and human calibration.
- [x] Verified primary-source bibliography, reconstructed official layout, compiled research PDF and appendices.
- [ ] Final human side-by-side template and scientific review.
- [ ] Sanitized empirical data reviewed before publication.

Follow README commands. The small included mock fixture under tests/fixtures/mock_run can be analyzed without inference. All generated results elsewhere are git-ignored. Do not merge mock/live sources. A checksum verifies bytes, not the truth of a scientific claim. Live pilot/batch availability is recorded in BUILD_STATUS.md; the included fixture remains mock-only.
