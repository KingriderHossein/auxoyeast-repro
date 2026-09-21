# Reproducibility log

This file is the central record of implementation, artifact, protocol, and numerical issues that can affect scientific reproducibility in this repository.

The purpose is to prevent important problems from being lost in notebook output, chat history, or local debugging. Every issue that can change a scientific result, alter interpretation, block exact reproduction, or affect execution stability should be recorded here.

## Logging policy

Each issue has:

- **ID**: stable identifier.
- **Category**: parsing, implementation, model artifact, protocol ambiguity, numerical behavior, upstream dependency, or validation design.
- **Status**: Open, Investigating, Mitigated, Resolved, or Documented.
- **Impact**: what scientific result or workflow component can be affected.
- **Evidence**: the observation that triggered the issue.
- **Decision / next action**: how the project handles the issue.
- **Scientific interpretation**: what may and may not be concluded from the issue.

Closed or mitigated issues remain in this file because they are part of the reproducibility history.

---

## R-001 — Exchange-target parser broke charged metabolite names

**Category:** Parsing  
**Status:** Resolved  
**Affected stage:** Dataset 2 parsing

### Evidence

The previous parser split exchange-target text on the character `+`. This incorrectly split charged compound names such as:

`thiamine(1+) exchange`

The affected record included Excel row 95, gene `YGR144W`, rescue reaction `r_2067`.

### Impact

A parser error could change the number or identity of rescue reactions and therefore alter phenotype classification.

### Resolution

The parser now counts explicit occurrences of the word `exchange` instead of splitting on `+`:

```python
def count_exchange_targets(value):
    if pd.isna(value):
        return 0
    text = str(value).strip()
    return len(re.findall(r"\bexchange\b", text, flags=re.I))
```

### Scientific interpretation

Results produced before this parser fix are not reference results.

---

## R-002 — Shared model state caused order-dependent phenotype behavior

**Category:** Implementation  
**Status:** Mitigated, under continued validation  
**Affected stage:** Auxotrophy benchmark

### Evidence

Exploratory runs reused a mutable COBRApy model across phenotype records. At least one THI6-related phenotype differed between a shared-state batch and an independently initialized model.

### Impact

Pair results could depend on simulation order rather than only on the requested gene knockout and medium.

### Mitigation

The reference workflow stopped reusing one mutable model directly across all pairs.

### Current caveat

The replacement strategy based on `Model.copy()` is itself under investigation because of R-006.

### Scientific interpretation

Shared-state exploratory batches must not be treated as reference benchmark results.

---

## R-003 — Repeated SBML reparsing caused late-run execution stalls

**Category:** Execution stability  
**Status:** Mitigated  
**Affected stage:** Auxotrophy benchmark

### Evidence

The original benchmark repeatedly called `read_sbml_model()` inside the 147-pair loop. The run reproducibly stalled late in the benchmark, including around the heme-region records.

A diagnostic run showed the stall occurring during model loading before knockout or optimization.

### Impact

The benchmark could fail to complete and checkpoint/resume behavior became difficult to distinguish from a biological or solver problem.

### Mitigation

The workflow was changed to load a pristine model once and isolate each phenotype from that base model.

### Current caveat

The `Model.copy()` implementation used for this mitigation is under investigation in R-006.

---

## R-004 — Dataset heme rescue identifier does not exist in original Yeast9

**Category:** Model artifact / dataset mapping  
**Status:** Documented  
**Affected stage:** Heme phenotypes

### Evidence

Dataset 2 uses rescue identifier `a_0001` for heme-related records.

The released original Yeast9 model does not contain this reaction identifier.

The curated model contains the added heme-a exchange reaction as `r_temp1`.

### Impact

Heme rescue behavior cannot be interpreted as a generic missing-ID software error. It reflects a difference between the dataset notation and released model artifacts.

### Decision

The workflow keeps model-specific alias handling explicit:

```python
ALIASES = {
    "Yeast9": {},
    "Yeast9_curated": {"a_0001": "r_temp1"},
}
```

### Scientific interpretation

The absence of `a_0001` in the original model is part of the artifact-level reproduction context and should remain visible in downstream interpretation.

---

## R-005 — Paper method and released MATLAB screening protocol are not identical

**Category:** Protocol discrepancy  
**Status:** Open  
**Affected stage:** Method reproduction

### Evidence

The article describes a default Yeast9 wild-type growth rate of approximately `0.0859` and uses 1% of the default wild-type growth as the viability threshold.

The released `code/gene_screen.m` first changes glucose exchange reaction `r_1714` to a lower bound of `-1000` before computing the reference wild-type growth.

This produces a materially different growth regime from the default model condition.

### Impact

"Paper method reproduction" and "released-script reproduction" are not necessarily the same experiment.

### Decision

The repository keeps these as separate protocols. The current primary benchmark follows the paper-described default wild-type condition.

### Scientific interpretation

Differences between these protocols must not be collapsed into a single reproduction result.

---

## R-006 — `Model.copy()` produces an inconsistent YPL214C knockout phenotype

**Category:** Implementation / numerical state  
**Status:** Investigating  
**Affected stage:** Curated-model auxotrophy benchmark  
**Primary affected record:** Excel row 96, `YPL214C`, thiamine  
**GitHub issue:** #8

### Evidence

Using a freshly loaded curated SBML model:

- associated reactions: `r_0556`, `r_1036`, `r_4753`
- all three bounds become `(0, 0)` after gene knockout
- knockout growth = `0`
- thiamine rescue growth is approximately `0.085835`
- phenotype classification = correct

Using `base_model.copy()`:

- the same three reaction bounds are reported as `(0, 0)`
- knockout growth is approximately `0.08583542`
- rescue growth is approximately `0.08583542`
- phenotype classification = Type I

Reassigning the copied model solver to GLPK does not remove the discrepancy.

### Impact

At least one current curated benchmark classification is not trustworthy under the `pristine_copy` isolation strategy.

The current `114/147` curated result therefore remains provisional until all 147 pairs are validated under a safer isolation method.

### Next action

Test COBRApy model-context isolation:

```python
with model:
    ...
```

If context isolation reproduces fresh-load behavior, rerun the complete benchmark with that method. Otherwise use stricter fresh-process or fresh-load isolation.

### Scientific interpretation

This issue is currently an implementation artifact candidate, not evidence of an error in the paper or biological model.

---

## R-007 — Two curated-model regressions follow the released r_0250 GPR

**Category:** Model artifact / curation behavior  
**Status:** Documented, interpretation pending  
**Affected records:** Excel rows 58 and 59

### Evidence

The curated model uses:

`(YOR303W AND YJR109C) OR YJL130C`

for reaction `r_0250`.

As a result, deleting either `YOR303W` or `YJR109C` individually leaves the `YJL130C` branch available.

Both fresh-load and copied-model diagnostics give approximately:

- knockout growth = `0.08638`
- classification = Type I

for:

- `YOR303W` / arginine add uracil
- `YJR109C` / arginine add uracil

### Impact

These two regressions appear to follow the released curated GPR rather than the `Model.copy()` anomaly.

### Scientific interpretation

They should be treated as released-model behavior until the paper, SBML, and MATLAB implementation are fully reconciled.

---

## R-008 — Released curated SBML and released curation script differ in selected edits

**Category:** Artifact discrepancy  
**Status:** Open  
**Affected stage:** Structural curation audit

### Evidence

The structural audit has identified selected differences between the released curated SBML and `auxoCurate.m`, including areas involving:

- `r_0172` and ALD2/ALD3 GPR handling
- `r_4702` / `r_4703` cysteine-related bounds
- `r_4048` stoichiometric coefficients
- selected GPR descriptions such as `r_0080`

### Impact

The article text, released MATLAB code, and released curated SBML cannot automatically be assumed to describe an identical final model state.

### Decision

Notebook 03 treats the released SBML as an independently audited artifact and keeps article/code/model evidence separate.

### Scientific interpretation

An artifact mismatch is not by itself evidence of author intent or publication error.

---

## R-009 — Dataset contains multi-gene records although the method describes single-gene knockout

**Category:** Protocol ambiguity  
**Status:** Documented  
**Affected stage:** Dataset 2 benchmark

### Evidence

Three records contain multiple genes:

- Excel row 72: `YPR074C and YBR117C`
- Excel row 73: `YDL131W and YDL182W`
- Excel row 74: `YNL104C and YOR108W`

The paper method describes single-gene knockout.

### Impact

A direct one-gene interpretation is impossible for these records without an explicit protocol choice.

### Decision

The current workflow treats all genes listed in one record as a joint knockout.

### Scientific interpretation

This is a documented protocol choice and should be included in any methods comparison.

---

## R-010 — Released MATLAB workflow has missing upstream dependencies

**Category:** Upstream dependency  
**Status:** Open  
**Affected stage:** Exact MATLAB-script reproduction

### Evidence

The released `code/gene_screen.m` expects `part_temp.xlsx`, which is not present in the available repository artifact.

The released `code/gene_sup.m` calls `changeRxnsModel`, which is also not present in the available repository artifact.

### Impact

The released MATLAB workflow cannot currently be reproduced end-to-end from the repository alone.

### Scientific interpretation

This is a reproducibility limitation of the released artifact set. It does not establish that the files did not exist in the authors' original environment.

---

## R-011 — Current benchmark counts differ from the paper

**Category:** Reproduction discrepancy  
**Status:** Investigating  
**Affected stage:** Headline benchmark  
**GitHub issue:** #9

### Evidence

Current provisional COBRApy + GLPK results:

- Yeast9: `92/147`
- Yeast9_curated: `114/147`

Paper-reported results:

- Yeast9: `93/147`
- Yeast9_curated: `117/147`

### Impact

The headline reproduction is not yet exact.

### Current interpretation

The curated `114/147` value is provisional because R-006 demonstrates at least one implementation-sensitive classification.

### Next action

Revalidate the full 147-pair benchmark under a safer isolation method before attributing the residual difference to solver, model, dataset, or paper artifacts.

---

## R-012 — Viability threshold and rescue uptake bound require sensitivity analysis

**Category:** Methodological sensitivity  
**Status:** Planned  
**Affected stage:** Phenotype classification

### Evidence

The current protocol uses:

- viability threshold = 1% of original Yeast9 wild-type growth
- supplement exchange lower bound = `-1000`

These values follow the interpreted paper protocol but are strong numerical choices.

### Impact

Phenotypes close to the threshold or dependent on unbounded nutrient uptake may be sensitive to these settings.

### Next action

Perform threshold and uptake-bound sensitivity after the reference implementation is stable.

---

## R-013 — The same phenotype dataset is used for curation and evaluation

**Category:** Validation design  
**Status:** Documented  
**Affected stage:** Interpretation of improved accuracy

### Evidence

The 147 gene-compound phenotype records are used to motivate/model curation and are also used to report post-curation benchmark accuracy.

### Impact

The reported improvement measures fit to the same benchmark set and is not equivalent to performance on an independent held-out validation set.

### Scientific interpretation

This does not invalidate the benchmark, but it limits how strongly the improvement can be generalized as out-of-sample predictive performance.

---

## R-014 — Dataset has 147 rows but 145 unique gene-compound pairs

**Category:** Dataset structure  
**Status:** Documented  
**Affected stage:** Accuracy interpretation

### Evidence

Dataset 2 contains 147 rows but 145 unique `(gene, chemical)` combinations because two serine-related pairs are duplicated.

### Impact

The headline accuracy is row-weighted, so duplicated records contribute more than once.

### Decision

The primary reproduction preserves all 147 rows to match the published benchmark denominator. Unique-pair analysis may be reported separately as a sensitivity check.

---

## Current blocking issue

The main blocker is **R-006**. No new headline benchmark result should be treated as final until the model-isolation behavior is validated across the full dataset.

## Update rule

When a new reproducibility-relevant problem is discovered:

1. Add or update an entry in this file before treating downstream results as final.
2. Open a GitHub Issue when the problem is unresolved and can change scientific results or block exact reproduction.
3. Link the resolving commit or pull request when the issue is fixed.
4. Keep the original entry after resolution so the project retains a complete scientific audit trail.
