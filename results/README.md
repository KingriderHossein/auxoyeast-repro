# Results and provenance

Most generated analysis outputs in this directory are local working artifacts and remain excluded from Git.

A small allowlisted set of benchmark outputs may be versioned when they are intended to support a scientific result. Final pair-result CSVs are authoritative only when the matching provenance sidecar exists and validates against the current benchmark signature.

For each final pair-result CSV, the workflow writes a sidecar:

- `02_Yeast9_pair_results.meta.json`
- `02_Yeast9_curated_pair_results.meta.json`

Each sidecar records the exact benchmark signature and payload, workflow commit, completed-pair count, and SHA-256 of the final CSV. A missing or mismatched sidecar means the corresponding CSV must be treated as stale or unverifiable, not as a current scientific result.

Checkpoint files remain local resumability artifacts. They are not substitutes for final provenance-bound outputs.

Keep any result you intend to cite or present tied to the corresponding notebook commit, environment, input hashes, and final-artifact metadata.

## Completed v0.5.8 evidence submitted for review

The completed outputs contain 147 pairs per model: 92 correct for Yeast9 and 116 for Yeast9_curated, with zero solver/input errors. See [the execution evidence note](../docs/v058_execution_evidence.md), the validation report, and artifact index. The assembled notebook records split direct-Python cell execution. Timing evidence supports a suspension contribution to the long YDL205C elapsed duration; exact timeout enforcement remains unresolved. Scientific acceptance and issue closure remain with Master.
