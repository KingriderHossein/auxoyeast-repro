# v0.5.8 completed execution evidence
Document version: 1.0.0

This evidence package preserves two completed runs of unchanged Notebook 02 code. It is submitted for Master review. Scientific acceptance and integration are separate decisions.

## Identities

- Assignment: 27-r1-g1-v058-persist-20261003-c7e4b1a9; Worker: auxoyeast-v058-results-worker-01.
- Contract: https://github.com/KingriderHossein/auxoyeast-repro/issues/27#issuecomment-5963434750
- Scientific execution commit: feaabea5d4408d14f15aee47da5399f5d2130be8; workflow version: 0.5.8.
- The later artifact-publication commit does not replace the scientific execution commit in provenance.
- Reference: Python 3.12.14, COBRApy 0.30.0, pandas 2.3.3, NumPy 2.5.3, SciPy 1.18.1, python-libSBML 5.21.1, optlang 1.9.1, swiglpk 5.0.13, GLPK 5.0.
- Primary GLPK feasibility tolerance: 1e-7; solver timeout: 180 s; process timeout: 240 s.
- Retry: only after primary process_timeout; same model/mapping/threshold/solver, feasibility tolerance 1e-9, process timeout 120 s.

## Measured outcomes

| Model | Pairs | Correct | Type I | Type II | Solver/input errors | Accuracy | Supplied paper reference |
|---|---:|---:|---:|---:|---:|---:|---:|
| Yeast9 | 147 | 92 | 37 | 18 | 0 / 0 | 62.5850% | 93 / 147 |
| Yeast9_curated | 147 | 116 | 28 | 3 | 0 / 0 | 78.9116% | 117 / 147 |

Both counts remain one below the supplied article claims. These are observed reproduction results, not evidence of an article error. R-011 / #9 remains open. The unchanged summary cell reports 26 fixed pairs, 2 regressions, and 119 unchanged pairs relative to original Yeast9. The two regressions are the known arginine/add-uracil records; this step does not investigate them.

## Actual full-run controls

| Model | YPL214C / thiamine | YPL028W / ergosterol | YDL205C / heme | YOR278W / heme |
|---|---|---|---|---|
| Yeast9 | correct; primary | type_I; primary | type_II; primary | type_II; primary |
| Yeast9_curated | correct; primary | correct; primary | correct; timeout retry | correct; timeout retry |

The curated heme retries are the only changes in classification versus provenance-checked v0.5.7 outputs: solver_error becomes correct at excel:139 and excel:140. Original-model classifications are unchanged.

## Validation and execution mode

The original validator v1.0.0 was executed with Python -B on the two scientific source worktrees and wrote a new report without overwrite. All 22 original-model checks and 23 curated-model checks passed; original dirty-worktree preservation also passed. The report recomputes classes, hashes and payload signatures and compares checkpoints, final CSVs, sidecars and contexts. Dataset 2 identities and mappings were independently checked in the preceding read-only reconciliation and are checked again by the persisted package verifier.

The existing finalizer v1.0.0 then ran on the isolated assembly worktree before its first commit. It loaded existing CSVs and templates, executed setup/definition cells 1-4 and unchanged summary cell 8, and did not execute model-preparation/optimization/benchmark cells 5-7.

results/02_v058_executed.ipynb combines outputs from two independent reference-Python processes with the new summary output. This is split direct-Python cell execution, not a single Jupyter-kernel run. Source cells remain identical to Notebook 02 at the execution commit. Cell 0 retains its old 0.5.5 display heading; the executable workflow version and signatures are 0.5.8.

## Timing evidence and remaining runtime limit

The curated YDL205C pair records 09h 59m 02s (35942 seconds, rounded down). A bounded System-event query found:
- Kernel-Power event 42, record 101749: 2026-10-01T12:55:05.3663285Z.
- Power-Troubleshooter event 1, record 101761: SleepTime 2026-10-01T12:55:04.8782036Z; WakeTime 2026-10-01T22:50:20.0592390Z.
- Kernel-General event 1, record 101751: OldTime 2026-10-01T12:55:07.9417811Z; NewTime 2026-10-01T22:50:18.5000000Z; TimeDeltaInMs 35710558.
- Kernel-Power event 107, record 101750, carries a pre-adjustment timestamp; event record order and the explicit SleepTime/WakeTime are retained.

The sleep/wake interval is 35715.181036 seconds. Subtracting it from the rounded pair duration leaves 226.818964 seconds. This arithmetic supports suspension as a major contribution to the long elapsed duration. It does not measure active execution time or prove how Python's timeout behaved across suspension. The exact timeout-enforcement question remains unresolved. No strict 240-second wall-time guarantee is asserted, and R-019 / #27 remains open.

The machine's event evidence, selected run-log lines, and original contexts are retained in the package. No cause is inferred from event identifiers alone.

## Byte integrity and preservation

The original CSVs contain CRLF and core.autocrlf=true would otherwise alter bytes during staging. Exact-path -text attributes protect only this package's artifacts and archived helper sources; global Git settings are unchanged. The package verifier checks local, staged and fetched-remote bytes against the artifact index and sidecars. Checkpoints and model caches remain local; templates were copied byte-for-byte for assembly and were not regenerated.

Source execution files are checked against the captured hashes in results/02_v058_source_preservation.json. The original historical worktree remains at 929942bcfefbef69806e28d95451261d4401b87f with its seven modified files.

## روند استدلال

Current GitHub identity and actual source artifacts establish the run identity. Independent row counts, Dataset 2 mappings, matching hashes, and recomputed signatures support preserving the existing complete runs. Re-execution would add no required evidence for this packaging task and is outside its scope. The residual count differences and unresolved timeout-enforcement limit remain visible. Artifact checks support review readiness; Master retains scientific acceptance.

## Review tools

- scripts/validate_v058_artifacts_v1.py and scripts/finalize_v058_results_v1.py are exact copies of the inspected helpers that produced this package.
- scripts/verify_v058_persisted_artifacts_v1.py checks package files without optimization. Use --revision INDEX for staged blobs and --revision <fetched-ref-or-SHA> for Git objects.
- results/02_v058_artifact_index.json records actual artifact byte counts and SHA-256 values.
