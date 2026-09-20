from __future__ import annotations

import pandas as pd


def summarize_results(results: pd.DataFrame, threshold: float) -> dict:
    return {
        "n": len(results),
        "correct": int((results["classification"] == "correct").sum()),
        "type_I": int((results["classification"] == "type_I").sum()),
        "type_II": int((results["classification"] == "type_II").sum()),
        "solver_error": int((results["classification"] == "solver_error").sum()),
        "input_error": int((results["classification"] == "input_error").sum()),
        "ko_dead": int(
            (
                (results["ko_status"] == "optimal")
                & (results["ko_growth"] < threshold)
            ).sum()
        ),
        "missing_background_rows": int(
            results["missing_background"].fillna("").ne("").sum()
        ),
        "missing_rescue_rows": int(
            results["missing_rescue"].fillna("").ne("").sum()
        ),
    }


def compare_pair_results(
    original_results: pd.DataFrame,
    curated_results: pd.DataFrame,
) -> pd.DataFrame:
    merged = original_results.merge(
        curated_results,
        on="pair_id",
        suffixes=("_original", "_curated"),
        validate="one_to_one",
    )

    def label(row) -> str:
        original_ok = row["classification_original"] == "correct"
        curated_ok = row["classification_curated"] == "correct"

        if not original_ok and curated_ok:
            return "fixed"
        if original_ok and not curated_ok:
            return "regression"
        return "unchanged"

    merged["change"] = merged.apply(label, axis=1)
    return merged
