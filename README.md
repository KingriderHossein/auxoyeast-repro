# AuxoYeast Reproducibility Audit

Professional COBRApy-based reproducibility audit of the auxotrophy curation reported by Han et al. (2024) for the Yeast9 genome-scale metabolic model.

## Scope

This repository separates three questions:

1. **Published-method reproduction** using the released Yeast9 models and Dataset 2.
2. **Released-artifact audit** comparing the original and curated SBML models.
3. **Upstream-code sensitivity** for differences between the article Methods and the authors' released MATLAB scripts.

The paper used MATLAB, COBRA Toolbox, and Gurobi. The default local implementation here uses COBRApy 0.30 and GLPK, with solver choice recorded in the run manifest.

## Repository layout

```text
auxoyeast-repro/
├─ src/auxoyeast_repro/      # reusable audit package
├─ notebooks/                # analysis notebooks; no duplicated core logic
├─ tests/                    # fast tests independent of large model files
├─ docs/                     # technical audit notes
├─ data/raw/                 # local study inputs; git-ignored
├─ results/                  # generated outputs; git-ignored
├─ environment.yml
├─ pyproject.toml
└─ .github/workflows/ci.yml
```

## Local setup

```bash
git clone https://github.com/KingriderHossein/auxoyeast-repro.git
cd auxoyeast-repro
conda env create -f environment.yml
conda activate auxoyeast-repro
```

Place the released study artifacts in `data/raw/`:

```text
data/raw/yeast9.0.xml
data/raw/Yeast9_curated.xml
data/raw/mmc3.xlsx
```

## Run

Strict isolated mode is the reference audit mode:

```bash
auxoyeast-audit --root . --solver glpk --isolation-mode reload
```

A faster QC mode copies an untouched model template per record:

```bash
auxoyeast-audit --root . --solver glpk --isolation-mode copy
```

Progress, ETA, checkpointing, and protocol signatures are built in. Results are written to `results/`.

## Scientific safeguards

- Stable `pair_id` values for every gene-compound record.
- Original/curated comparison by key, never row position.
- Non-optimal solver states are reported as `solver_error`, never silently converted to zero growth.
- Conditional-medium records are parsed explicitly into rescue and background nutrients.
- Input files are SHA-256 hashed in the manifest.
- Checkpoints are tied to model/data/config signatures.
- Strict mode prevents phenotype carry-over between simulations.

## Paper reference values

The publication reports 93/147 correct predictions for Yeast9 and 117/147 for the curated model. These are reference claims, not hard-coded expected test results.

## Development

```bash
pip install -e ".[dev]"
pre-commit install
ruff check .
ruff format --check .
pytest
```

Core logic belongs in `src/auxoyeast_repro/`. Notebooks should orchestrate and visualize the package rather than reimplement simulation functions.

## Citation

Han S, Wu K, Wang Y, Li F, Chen Y. Auxotrophy-based curation improves the consensus genome-scale metabolic model of yeast. *Synthetic and Systems Biotechnology*. 2024;9:861-870. DOI: 10.1016/j.synbio.2024.07.006.

## License

Repository-authored code is released under the MIT License. Upstream models, datasets, article content, and third-party code remain subject to their original licenses and citation requirements.
