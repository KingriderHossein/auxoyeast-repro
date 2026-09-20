# AuxoYeast Reproducibility Audit

Scientific, notebook-first reproducibility audit of the auxotrophy-based curation reported by Han et al. (2024) for the Yeast9 genome-scale metabolic model.

## Project type

This repository is a **bioinformatics / computational systems biology research project**, not a software product.

The primary research record is a sequence of Jupyter notebooks. Each notebook contains the code, outputs, interpretation, and provenance needed for one scientific question.

## Research questions

1. Does the released Yeast9 model reproduce the wild-type growth and auxotrophy protocol reported in the paper?
2. Can the 147 gene-compound benchmark be reproduced with pair-isolated COBRApy simulations?
3. Do the released original and curated SBML models contain the structural changes described in the paper?
4. Which differences remain between the paper, released models, released MATLAB code, and COBRApy reproduction?

## Repository layout

```text
auxoyeast-repro/
├── notebooks/
│   ├── 01_model_validation.ipynb
│   ├── 02_auxotrophy_reproduction.ipynb
│   ├── 03_curation_audit.ipynb
│   ├── 04_paper_discrepancies.ipynb
│   └── 05_final_results.ipynb
├── data/
│   └── raw/                  # local-only released artifacts
├── results/                  # local-only generated outputs
├── docs/
│   └── code_and_paper_audit.md
├── environment.yml
├── CITATION.cff
├── LICENSE
└── README.md
```

## Required local input files

Place the released study artifacts in:

```text
data/raw/yeast9.0.xml
data/raw/Yeast9_curated.xml
data/raw/mmc3.xlsx
```

These files are intentionally not versioned in this repository. The notebooks record SHA-256 hashes so each local analysis remains traceable to the exact input artifacts used.

## Local setup in VS Code

```bash
git clone https://github.com/KingriderHossein/auxoyeast-repro.git
cd auxoyeast-repro
conda env create -f environment.yml
conda activate auxoyeast-repro
python -m ipykernel install --user --name auxoyeast-repro --display-name "Python (auxoyeast-repro)"
code .
```

In VS Code, select the kernel:

```text
Python (auxoyeast-repro)
```

## Notebook order

Run the notebooks in order:

1. **01_model_validation.ipynb**  
   Validate input files, model dimensions, objective, solver status, wild-type growth, and the 1% viability threshold.

2. **02_auxotrophy_reproduction.ipynb**  
   Parse Dataset 2, run the 147 gene-compound benchmark in strict isolated mode, save checkpoints, and compare original versus curated phenotypes.

3. **03_curation_audit.ipynb**  
   Audit reaction bounds, GPR rules, added reactions, and selected stoichiometric changes in the released curated SBML.

4. **04_paper_discrepancies.ipynb**  
   Compare reproduced results with reported paper values and maintain an explicit discrepancy register.

5. **05_final_results.ipynb**  
   Generate clean summary tables and figures for interpretation and presentation.

## Scientific safeguards

The notebook workflow follows these rules:

- Parse released spreadsheet columns by name, not column position.
- Use stable pair identifiers for comparisons.
- Keep every gene-compound simulation independent by copying a pristine model object for each pair.
- Do not convert solver failures into biological zero growth.
- Preserve conditional-medium information explicitly.
- Record input hashes, package versions, solver, and threshold.
- Save long-running benchmark checkpoints locally.
- Keep the published-method reproduction separate from sensitivity analyses based on the released MATLAB scripts.
- Treat intermediate debugging results as provisional until the strict isolated run is complete.

## Environment

The current reference environment uses:

- Python 3.12
- COBRApy 0.30
- GLPK through `swiglpk`
- pandas
- NumPy
- SciPy
- python-libSBML
- openpyxl
- matplotlib
- Jupyter / ipykernel

The paper used MATLAB, COBRA Toolbox, and Gurobi. Solver differences must therefore be considered when interpreting any remaining numerical discrepancy.

## Paper reference values

The publication reports:

- Yeast9: 93 / 147 correct predictions
- Yeast9 curated: 117 / 147 correct predictions
- accuracy: 63.27% -> 79.59%

These values are reference claims. They are not hard-coded as expected test outcomes.

## Reference

Han S, Wu K, Wang Y, Li F, Chen Y. *Auxotrophy-based curation improves the consensus genome-scale metabolic model of yeast.* Synthetic and Systems Biotechnology. 2024;9:861-870. DOI: 10.1016/j.synbio.2024.07.006.

## Version

Notebook workflow version: **0.5.2**
