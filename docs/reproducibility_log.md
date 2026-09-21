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

## R-006 — Model isolation can produce inconsistent knockout/rescue phenotypes

**Category:** Implementation / numerical state  
**Status:** Investigating  
**Affected stage:** Curated-model auxotrophy benchmark  
**Primary affected records:** Excel row 96, `YPL214C`, thiamine; context-sequence check also affected Excel row 123, `YPL028W`, ergosterol  
**GitHub issue:** #8

### Evidence

Using a freshly loaded curated SBML model for `YPL214C`:

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

Reassigning the copied model solver to GLPK does not remove the discrepancy. A later sequential `with model:` context test also reproduced the incorrect YPL214C knockout growth, so simple in-process context reuse is not a valid replacement strategy (see R-015).

A second diagnostic reused one freshly loaded model with a COBRApy context for each test case:

```python
with model:
    ...
```

This did **not** reproduce fresh-load behavior for all cases:

- `YPL214C`: knockout growth remained approximately `0.085835` instead of `0`
- `YPL028W`: knockout growth was `0`, but ergosterol rescue became `0` instead of approximately `0.088461`
- `YOR303W` and `YJR109C`: behavior remained stable and consistent with the released curated `r_0250` GPR
- `YGR204W` and `YGR144W`: classifications remained consistent with fresh-load checks

The `YPL028W` result shows that sequential context use can retain or produce state inconsistent with a freshly reconstructed model even when the Python-level context exits normally.

### Impact

Both the `pristine_copy` and sequential `model_context` isolation strategies are unsuitable as reference methods until their state behavior is understood.

The current `114/147` curated benchmark remains provisional. No headline benchmark count should be treated as final while this issue is open.

### Next action

Test a reconstruction-based isolation strategy that avoids both solver deepcopy and repeated SBML parsing:

1. Load the released SBML once.
2. Serialize the pristine COBRA model once with `cobra.io.to_json()`.
3. Reconstruct a new model for each phenotype with `cobra.io.from_json()`.
4. Compare focused cases against independent fresh-SBML loads.
5. If they agree, rerun all 147 pairs using JSON reconstruction and verify selected records again with fresh-SBML loads.

COBRApy's JSON loader constructs a new `Model`, adds metabolites, genes, and reactions, and then rebuilds the objective. This makes it a useful candidate for fresh solver/model reconstruction without repeatedly invoking libSBML.

### Scientific interpretation

This issue is currently a local implementation/isolation problem. It is not evidence of an error in the article or in the biological curation until a stable reconstruction method establishes the reference phenotype results.

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


## R-015 — Sequential `with model:` contexts do not provide reliable pair isolation

**Category:** Implementation / solver-state isolation  
**Status:** Investigating  
**Affected stage:** Auxotrophy benchmark  
**GitHub issue:** #12

### Evidence

A single freshly loaded curated model was reused across six diagnostic cases, with each phenotype wrapped in a separate COBRApy model context.

Selected results:

- `YGR204W`: knockout approximately zero; rescue approximately `0.087317` — consistent with fresh reload.
- `YGR144W`: knockout approximately `0.08583537`; rescue approximately `0.085835` — consistent with fresh reload.
- `YPL214C`: knockout approximately `0.08583537`; rescue approximately `0.085835` — inconsistent with fresh reload, where knockout growth is zero.
- `YPL028W`: knockout zero; rescue zero — inconsistent with fresh reload, where ergosterol rescue is approximately `0.088461`.
- `YOR303W` and `YJR109C`: both remain Type I and match fresh-load behavior.

The `YPL028W` result is especially important because the rescue phenotype changed only after earlier contexts had been executed, demonstrating order-dependent contamination in the reused in-process model.

### Impact

COBRApy context management cannot currently be treated as sufficient scientific isolation for this benchmark workflow.

Together with R-006, this means both tested in-process reuse strategies are unsafe as reference methods:

- `base_model.copy()`
- repeated `with model:` contexts on one model instance

### Decision

Do not rerun the reference 147-pair benchmark with sequential model contexts.

The next isolation strategy must construct a genuinely fresh COBRApy model/solver state for each pair without repeatedly invoking libSBML in one long-lived process.

### Next action

Evaluate a fresh-deserialization strategy, preferably a validated COBRApy JSON round-trip generated from the released SBML, and compare it pair-by-pair against fresh SBML loads on the diagnostic cases before running the complete benchmark.

If JSON reconstruction is not equivalent, use process-level isolation so each pair reads SBML in a fresh Python process.

### Scientific interpretation

This is a local implementation/state-management issue. It does not provide evidence about the correctness of the article or released biological model.



## R-016 — COBRApy JSON round-trip is not phenotype-equivalent to the released SBML

**Category:** Serialization / model artifact  
**Status:** Documented; not a current benchmark blocker  
**Affected stage:** Rejected candidate per-pair isolation strategy  
**GitHub issue:** #14

### Evidence

A fresh curated Yeast9 model loaded from SBML was saved with `save_json_model()` and reconstructed with `load_json_model()`. Six difficult phenotype cases were then compared using a fresh model instance for each case.

Five cases matched fresh SBML behavior closely:

- `YGR204W`
- `YGR144W`
- `YPL214C`
- `YOR303W`
- `YJR109C`

However, `YPL028W` / ergosterol did not match:

- fresh SBML: knockout growth = `0`, rescue growth approximately `0.088461`
- fresh JSON: knockout growth = `0`, rescue growth = `0`

### Impact

A COBRApy JSON cache cannot currently be used as the reference fresh-model reconstruction method for the full 147-pair benchmark.

The failure is phenotype-specific and would silently convert a rescued phenotype into Type II if JSON reconstruction were used without validation.

### Technical note

COBRApy JSON serialization stores the standard model structure (metabolites, reactions, genes, bounds, GPRs, objective coefficients, and selected metadata), but it does not guarantee preservation of every solver-level or SBML-specific state that may exist after SBML import.

### Decision

Reject JSON round-trip as a reference benchmark isolation strategy until the `YPL028W` discrepancy is explained.

### Next action

JSON-specific diagnosis is deferred because the benchmark no longer depends on JSON reconstruction. The reference candidate is now process-level isolation: one fresh Python process, one fresh SBML load, and one phenotype simulation per process. JSON can be revisited later if the serialization mismatch itself becomes scientifically relevant.

### Scientific interpretation

This is a local serialization/reconstruction issue. It is not evidence of an error in the paper or biological model.


## Current blocking issue

The main blockers are **R-006** and **R-015**. R-016 remains documented but is no longer a benchmark blocker because JSON reconstruction has been rejected as a reference strategy. No new headline benchmark result should be treated as final until process-level fresh-SBML isolation is validated and used across the full dataset.

## Update rule

When a new reproducibility-relevant problem is discovered:

1. Add or update an entry in this file before treating downstream results as final.
2. Open a GitHub Issue when the problem is unresolved and can change scientific results or block exact reproduction.
3. Link the resolving commit or pull request when the issue is fixed.
4. Keep the original entry after resolution so the project retains a complete scientific audit trail.
