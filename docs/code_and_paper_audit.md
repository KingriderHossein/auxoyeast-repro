# Code and paper audit notes

## Purpose

This project is a reproducibility audit of Han et al. (2024), not a tutorial reimplementation.

## Methodological decisions

- The published method is treated separately from the authors' released MATLAB scripts.
- The primary benchmark uses the released Yeast9 SBML models and Dataset 2.
- Each gene-compound record is isolated from previous records in strict `reload` mode.
- Solver failures are never converted silently into biological zero-growth phenotypes.
- Conditional-medium records are parsed into rescue nutrients and background supplements.
- Input files and protocol settings are fingerprinted for provenance and checkpoint safety.

## Known issues identified during development

1. A shared COBRApy model object produced state-dependent behavior in exploratory batch runs. The reference implementation therefore uses strict per-record isolation.
2. Early code used positional spreadsheet columns and positional DataFrame alignment. The production implementation uses named columns and stable `pair_id` joins.
3. The paper reports MATLAB + COBRA Toolbox + Gurobi, while this repository defaults to COBRApy + GLPK. Solver sensitivity must be evaluated before assigning discrepancies to the publication.
4. The article, released curated SBML, and released MATLAB curation code contain artifact-level differences that should be audited independently of phenotype benchmarking.

## Interpretation rule

Do not call a numerical mismatch a paper error until model QC, dataset parsing, solver status, isolation, and solver sensitivity have all been checked.
