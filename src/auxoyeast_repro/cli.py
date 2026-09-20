from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .config import AuditConfig, ProjectPaths
from .dataset import parse_dataset
from .models import load_model, model_qc
from .provenance import build_provenance, write_manifest
from .reporting import compare_pair_results, summarize_results
from .simulation import run_benchmark


PAPER_REPORTED = {
    "Yeast9": {
        "correct": 93,
        "n": 147,
        "accuracy": 93 / 147,
        "ko_dead": 107,
    },
    "Yeast9_curated": {
        "correct": 117,
        "n": 147,
        "accuracy": 117 / 147,
        "ko_dead": 119,
    },
}

MODEL_ALIASES = {
    "Yeast9": {},
    "Yeast9_curated": {"a_0001": "r_temp1"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the AuxoYeast reproducibility audit"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--solver", default="glpk")
    parser.add_argument(
        "--isolation-mode",
        choices=["reload", "copy"],
        default="reload",
    )
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = ProjectPaths(args.root.resolve())
    paths.ensure_output_dir()

    config = AuditConfig(
        solver=args.solver,
        isolation_mode=args.isolation_mode,
    )
    config.validate()

    missing = [path for path in paths.required_inputs() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required inputs:\n"
            + "\n".join(f"- {path}" for path in missing)
        )

    original = load_model(paths.original_xml, config.solver)
    curated = load_model(paths.curated_xml, config.solver)

    qc = pd.DataFrame(
        [
            model_qc(original, "Yeast9"),
            model_qc(curated, "Yeast9_curated"),
        ]
    )
    qc.to_csv(paths.output_dir / "model_qc.csv", index=False)

    if not (qc["status"] == "optimal").all():
        raise RuntimeError("At least one model failed wild-type optimization")

    wt_original = float(
        qc.loc[qc["model"] == "Yeast9", "wt_growth"].iloc[0]
    )
    threshold = config.viability_fraction * wt_original

    pairs = parse_dataset(paths.dataset_xlsx)
    if len(pairs) != 147:
        raise AssertionError(f"Expected 147 pairs, found {len(pairs)}")

    original_results = run_benchmark(
        model_path=paths.original_xml,
        dataset_path=paths.dataset_xlsx,
        model_label="Yeast9",
        pairs_df=pairs,
        threshold=threshold,
        aliases=MODEL_ALIASES["Yeast9"],
        output_dir=paths.output_dir,
        config=config,
        resume=not args.no_resume,
        progress=not args.no_progress,
    )

    curated_results = run_benchmark(
        model_path=paths.curated_xml,
        dataset_path=paths.dataset_xlsx,
        model_label="Yeast9_curated",
        pairs_df=pairs,
        threshold=threshold,
        aliases=MODEL_ALIASES["Yeast9_curated"],
        output_dir=paths.output_dir,
        config=config,
        resume=not args.no_resume,
        progress=not args.no_progress,
    )

    summary = pd.DataFrame(
        [
            {
                "model": "Yeast9",
                **summarize_results(original_results, threshold),
            },
            {
                "model": "Yeast9_curated",
                **summarize_results(curated_results, threshold),
            },
        ]
    )
    summary["accuracy"] = summary["correct"] / summary["n"]
    summary.to_csv(paths.output_dir / "summary.csv", index=False)

    pairwise = compare_pair_results(
        original_results,
        curated_results,
    )
    pairwise.to_csv(
        paths.output_dir / "pairwise_change_audit.csv",
        index=False,
    )

    provenance = build_provenance(
        list(paths.required_inputs()),
        config,
    )
    write_manifest(
        paths.output_dir / "manifest.json",
        {
            "package_version": "0.4.0",
            "analysis_label": (
                "paper-method reproduction using released artifacts"
            ),
            "viability_threshold": threshold,
            "paper_reported": PAPER_REPORTED,
            "provenance": provenance,
        },
    )

    print("\nSummary")
    print(summary.to_string(index=False))
    print(f"\nResults: {paths.output_dir}")


if __name__ == "__main__":
    main()
