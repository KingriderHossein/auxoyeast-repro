# Code and paper audit notes

## Purpose

The central issue history for reproducibility-relevant problems is maintained in [`reproducibility_log.md`](reproducibility_log.md). Open scientific or implementation problems that can change benchmark results should be recorded there before downstream conclusions are treated as final.


This repository is a scientific reproducibility audit of Han et al. (2024). It is intentionally notebook-first so that code, outputs, interpretation, and provenance remain visible in one research record.

## Analysis layers

The project keeps four layers separate:

1. **Model validation**  
   Confirm input identity, model dimensions, objective, solver status, wild-type growth, and viability threshold.

2. **Auxotrophy benchmark reproduction**  
   Reproduce the 147 gene-compound phenotype benchmark with isolated simulations.

3. **Structural curation audit**  
   Compare reaction bounds, GPR rules, added reactions, and selected stoichiometric edits between the released original and curated SBML models.

4. **Paper/artifact discrepancy analysis**  
   Compare paper claims with released models, released MATLAB code, and the COBRApy reproduction without treating any mismatch as a publication error until implementation and solver effects have been excluded.

## Methodological decisions

- The published method is treated separately from the authors' released MATLAB scripts.
- The primary phenotype benchmark uses the released Yeast9 SBML models and Dataset 2.
- Each released SBML model is parsed once into a validated solver-independent COBRA JSON template. Each gene-compound record is then executed in a fresh Python process that reconstructs a new COBRA model and optimization backend from that JSON template.
- Solver failures are not converted silently into biological zero-growth phenotypes.
- Conditional-medium records are parsed into rescue nutrients and background supplements.
- Input files are fingerprinted with SHA-256.
- Long runs use local checkpoints and can be resumed.
- Original and curated results are joined by stable pair identifiers, never by row position.

## Known development issue

A shared COBRApy model object produced state-dependent behavior during exploratory batch runs. A THI6 phenotype differed between a shared-state batch and a fresh-model run. The reference workflow therefore performs pair-isolated simulations.

## Paper implementation caveat

The paper reports MATLAB + COBRA Toolbox + Gurobi. The local reference environment currently uses COBRApy + GLPK. Solver sensitivity must be considered before assigning residual numerical differences to the released study artifacts.

## Interpretation rule

Do not classify a numerical mismatch as a paper error until model QC, dataset parsing, solver status, pair isolation, and solver sensitivity have been checked.


## Runtime stability note

Repeatedly reparsing the same large SBML file inside the 147-pair loop caused a reproducible stall late in the original-model benchmark. Subsequent copy-based and sequential-context approaches avoided that parser stall but were rejected after the curated THI6/YPL214C phenotype produced a viable knockout despite reaction and solver-variable bounds being visibly closed. The reference workflow therefore avoids repeated SBML parsing, model copying, and solver reuse.


## Runtime diagnosis and final isolation strategy (v0.5.4)

A reproducible timeout was isolated to the fresh-process SBML-loading path for the HEM12/heme record (excel:137). A direct diagnostic on an already loaded pristine Yeast9 model showed that model copying (~1 s), YDR047W knockout, and GLPK optimization (~0.04 s) complete normally, while the rescue ID `a_0001` is absent from original Yeast9. This excludes the biological knockout and GLPK solve as the source of the 180 s timeout.

The reference benchmark therefore loads each SBML model once and creates an independent `model.copy()` for every gene-compound pair. The pristine base model is fingerprinted from objective direction, objective coefficients, all reaction bounds, and all gene functional states; the fingerprint is checked after every pair. A per-solver timeout remains enabled.


## Final isolation protocol (v0.5.5)

The project deliberately stops the sequence of ad hoc isolation experiments here. The reference protocol is now fixed to a fresh-process JSON reconstruction design:

1. Parse each released SBML file exactly once.
2. Export the parsed COBRA network to a local JSON template.
3. Reload the JSON template and validate model dimensions, objective, and wild-type growth against the source SBML.
4. Validate the curated THI6/YPL214C knockout as a sentinel before any 147-pair batch run.
5. For every gene-compound pair, launch a fresh Python process, load a new COBRA model from the validated JSON template, create a fresh solver backend, perform the knockout and supplementation simulation, emit one result, and terminate the process.

This protocol is intended to remove both failure modes observed during development: repeated libSBML parser instability and solver-state inconsistencies introduced by model copying or sequential reuse.

The previous v0.5.4 pristine-copy results are retained as diagnostic evidence, not as the reference benchmark. Residual GLPK time limits, if any, are recorded as solver sensitivity and are not silently converted into biological predictions.
