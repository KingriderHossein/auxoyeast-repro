from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from typing import Optional
import json
import time

import numpy as np
import pandas as pd

from .config import AuditConfig
from .models import load_model, solve_growth
from .provenance import sha256_file


def resolve_reaction_id(
    model,
    reaction_id: str,
    aliases: dict[str, str],
) -> Optional[str]:
    if reaction_id in model.reactions:
        return reaction_id
    alias = aliases.get(reaction_id)
    if alias is not None and alias in model.reactions:
        return alias
    return None


def open_uptake(model, reaction_id: str, lower_bound: float) -> None:
    model.reactions.get_by_id(reaction_id).lower_bound = float(lower_bound)


def classify_auxotrophy(
    ko_status: str,
    ko_growth: float,
    rescue_status: str,
    rescue_growth: float,
    threshold: float,
) -> str:
    if ko_status != "optimal" or rescue_status != "optimal":
        return "solver_error"
    if not np.isfinite(ko_growth) or not np.isfinite(rescue_growth):
        return "solver_error"
    if ko_growth >= threshold:
        return "type_I"
    if rescue_growth < threshold:
        return "type_II"
    return "correct"


def simulate_pair_on_model(
    model,
    record: dict,
    threshold: float,
    aliases: dict[str, str],
    uptake_lower_bound: float,
) -> dict:
    missing_genes = [gene for gene in record["genes"] if gene not in model.genes]
    if missing_genes:
        return {
            "pair_id": record["pair_id"],
            "excel_row": record["excel_row"],
            "gene_field": record["gene_field"],
            "chemical": record["chemical"],
            "strain_background": record["strain_background"],
            "n_genes": record["n_genes"],
            "missing_genes": "+".join(missing_genes),
            "mapped_background": "",
            "missing_background": "",
            "mapped_rescue": "",
            "missing_rescue": "",
            "ko_status": "input_error",
            "ko_growth": np.nan,
            "rescue_status": "input_error",
            "rescue_growth": np.nan,
            "classification": "input_error",
            "correct": False,
        }

    for gene in record["genes"]:
        model.genes.get_by_id(gene).knock_out()

    mapped_background: list[str] = []
    missing_background: list[str] = []
    for reaction_id in record["background_ids"]:
        resolved = resolve_reaction_id(model, reaction_id, aliases)
        if resolved is None:
            missing_background.append(reaction_id)
        else:
            open_uptake(model, resolved, uptake_lower_bound)
            mapped_background.append(resolved)

    ko_status, ko_growth = solve_growth(model)

    mapped_rescue: list[str] = []
    missing_rescue: list[str] = []
    for reaction_id in record["rescue_ids"]:
        resolved = resolve_reaction_id(model, reaction_id, aliases)
        if resolved is None:
            missing_rescue.append(reaction_id)
        else:
            open_uptake(model, resolved, uptake_lower_bound)
            mapped_rescue.append(resolved)

    rescue_status, rescue_growth = solve_growth(model)
    classification = classify_auxotrophy(
        ko_status,
        ko_growth,
        rescue_status,
        rescue_growth,
        threshold,
    )

    return {
        "pair_id": record["pair_id"],
        "excel_row": record["excel_row"],
        "gene_field": record["gene_field"],
        "chemical": record["chemical"],
        "strain_background": record["strain_background"],
        "n_genes": record["n_genes"],
        "missing_genes": "+".join(missing_genes),
        "mapped_background": "+".join(mapped_background),
        "missing_background": "+".join(missing_background),
        "mapped_rescue": "+".join(mapped_rescue),
        "missing_rescue": "+".join(missing_rescue),
        "ko_status": ko_status,
        "ko_growth": ko_growth,
        "rescue_status": rescue_status,
        "rescue_growth": rescue_growth,
        "classification": classification,
        "correct": classification == "correct",
    }


def _format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
    return f"{minutes:02d}m {seconds:02d}s"


def _run_signature(
    model_path: Path,
    dataset_path: Path,
    model_label: str,
    config: AuditConfig,
) -> str:
    payload = {
        "model_label": model_label,
        "model_sha256": sha256_file(model_path),
        "dataset_sha256": sha256_file(dataset_path),
        "config": asdict(config),
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return sha256(raw).hexdigest()


def run_benchmark(
    *,
    model_path: Path,
    dataset_path: Path,
    model_label: str,
    pairs_df: pd.DataFrame,
    threshold: float,
    aliases: dict[str, str],
    output_dir: Path,
    config: AuditConfig,
    resume: bool = True,
    progress: bool = True,
) -> pd.DataFrame:
    config.validate()
    output_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_csv = output_dir / f"checkpoint_{model_label}.csv"
    checkpoint_meta = output_dir / f"checkpoint_{model_label}.json"
    signature = _run_signature(model_path, dataset_path, model_label, config)

    completed = pd.DataFrame()
    completed_ids: set[str] = set()

    if resume and checkpoint_csv.exists() and checkpoint_meta.exists():
        metadata = json.loads(checkpoint_meta.read_text(encoding="utf-8"))
        if metadata.get("run_signature") != signature:
            raise RuntimeError(
                f"Checkpoint signature mismatch for {model_label}. "
                "Rename or remove the old checkpoint before changing the protocol."
            )
        completed = pd.read_csv(checkpoint_csv)
        completed_ids = set(completed["pair_id"].astype(str))

    pristine_template = None
    if config.isolation_mode == "copy":
        pristine_template = load_model(model_path, config.solver)

    new_results: list[dict] = []
    recent_times: list[float] = []
    session_start = time.perf_counter()

    for record in pairs_df.to_dict("records"):
        if record["pair_id"] in completed_ids:
            continue

        pair_start = time.perf_counter()

        if config.isolation_mode == "reload":
            model = load_model(model_path, config.solver)
        else:
            model = pristine_template.copy()
            model.solver = config.solver

        result = simulate_pair_on_model(
            model,
            record,
            threshold,
            aliases,
            config.uptake_lower_bound,
        )
        new_results.append(result)

        pair_seconds = time.perf_counter() - pair_start
        recent_times.append(pair_seconds)
        recent_times = recent_times[-config.eta_window :]

        current = pd.concat(
            [completed, pd.DataFrame(new_results)],
            ignore_index=True,
        ).drop_duplicates(subset=["pair_id"], keep="last")

        if len(new_results) % config.checkpoint_every == 0:
            current.sort_values("excel_row").to_csv(checkpoint_csv, index=False)
            checkpoint_meta.write_text(
                json.dumps(
                    {
                        "run_signature": signature,
                        "model_label": model_label,
                        "model_path": str(model_path),
                        "config": asdict(config),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        if progress:
            completed_count = len(current)
            remaining_count = len(pairs_df) - completed_count
            eta = float(np.mean(recent_times)) * remaining_count
            elapsed = time.perf_counter() - session_start
            print(
                f"\r{model_label}: {completed_count}/{len(pairs_df)} "
                f"({100 * completed_count / len(pairs_df):5.1f}%) | "
                f"pair={record['pair_id']} | gene={record['gene_field']} | "
                f"last={_format_duration(pair_seconds)} | "
                f"elapsed={_format_duration(elapsed)} | "
                f"eta={_format_duration(eta)}",
                end="",
                flush=True,
            )

    if progress:
        print()

    final = pd.concat(
        [completed, pd.DataFrame(new_results)],
        ignore_index=True,
    )
    final = (
        final.drop_duplicates(subset=["pair_id"], keep="last")
        .sort_values("excel_row")
        .reset_index(drop=True)
    )
    final.to_csv(output_dir / f"{model_label}_pair_results.csv", index=False)
    return final
