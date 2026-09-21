from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

from cobra.io import read_sbml_model


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run one auxotrophy phenotype in a fresh Python process."
    )
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-label", required=True)
    parser.add_argument("--solver", default="glpk")
    parser.add_argument("--threshold", required=True, type=float)
    parser.add_argument("--uptake-lower-bound", default=-1000.0, type=float)
    parser.add_argument("--gene", action="append", required=True)
    parser.add_argument("--background", action="append", default=[])
    parser.add_argument("--rescue", action="append", default=[])
    parser.add_argument("--aliases-json", default="{}")
    parser.add_argument("--pair-id", default="")
    return parser.parse_args()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_reaction_id(model, reaction_id, aliases):
    if reaction_id in model.reactions:
        return reaction_id
    alias = aliases.get(reaction_id)
    if alias is not None and alias in model.reactions:
        return alias
    return None


def solve_growth(model):
    value = model.slim_optimize(error_value=float("nan"))
    status = str(model.solver.status).lower()
    growth = float(value) if value is not None else float("nan")
    return status, growth


def classify_auxotrophy(ko_status, ko_growth, rescue_status, rescue_growth, threshold):
    if ko_status != "optimal" or rescue_status != "optimal":
        return "solver_error"
    if not math.isfinite(ko_growth) or not math.isfinite(rescue_growth):
        return "solver_error"
    if ko_growth >= threshold:
        return "type_I"
    if rescue_growth < threshold:
        return "type_II"
    return "correct"


def json_safe_number(value):
    if value is None or not math.isfinite(float(value)):
        return None
    return float(value)


def main():
    args = parse_args()
    model_path = Path(args.model_path).resolve()
    aliases = json.loads(args.aliases_json)

    model = read_sbml_model(str(model_path))
    model.solver = args.solver

    missing_genes = [gene for gene in args.gene if gene not in model.genes]
    if missing_genes:
        result = {
            "pair_id": args.pair_id,
            "model": args.model_label,
            "pid": os.getpid(),
            "python_executable": sys.executable,
            "model_path": str(model_path),
            "model_sha256": sha256_file(model_path),
            "solver": args.solver,
            "threshold": args.threshold,
            "uptake_lower_bound": args.uptake_lower_bound,
            "genes": "+".join(args.gene),
            "classification": "input_error",
            "correct": False,
            "ko_status": "input_error",
            "ko_growth": None,
            "rescue_status": "input_error",
            "rescue_growth": None,
            "missing_genes": "+".join(missing_genes),
            "mapped_background": "",
            "missing_background": "",
            "mapped_rescue": "",
            "missing_rescue": "",
            "associated_reactions": "",
            "bounds_after_knockout": {},
        }
        print(json.dumps(result, sort_keys=True))
        return

    associated_reactions = sorted(
        {
            reaction.id
            for gene_id in args.gene
            for reaction in model.genes.get_by_id(gene_id).reactions
        }
    )

    for gene_id in args.gene:
        model.genes.get_by_id(gene_id).knock_out()

    bounds_after_knockout = {
        reaction_id: list(model.reactions.get_by_id(reaction_id).bounds)
        for reaction_id in associated_reactions
    }

    mapped_background = []
    missing_background = []
    for reaction_id in args.background:
        resolved = resolve_reaction_id(model, reaction_id, aliases)
        if resolved is None:
            missing_background.append(reaction_id)
        else:
            model.reactions.get_by_id(resolved).lower_bound = args.uptake_lower_bound
            mapped_background.append(resolved)

    ko_status, ko_growth = solve_growth(model)

    mapped_rescue = []
    missing_rescue = []
    for reaction_id in args.rescue:
        resolved = resolve_reaction_id(model, reaction_id, aliases)
        if resolved is None:
            missing_rescue.append(reaction_id)
        else:
            model.reactions.get_by_id(resolved).lower_bound = args.uptake_lower_bound
            mapped_rescue.append(resolved)

    rescue_status, rescue_growth = solve_growth(model)

    classification = classify_auxotrophy(
        ko_status,
        ko_growth,
        rescue_status,
        rescue_growth,
        args.threshold,
    )

    result = {
        "pair_id": args.pair_id,
        "model": args.model_label,
        "pid": os.getpid(),
        "python_executable": sys.executable,
        "model_path": str(model_path),
        "model_sha256": sha256_file(model_path),
        "solver": args.solver,
        "threshold": args.threshold,
        "uptake_lower_bound": args.uptake_lower_bound,
        "genes": "+".join(args.gene),
        "classification": classification,
        "correct": classification == "correct",
        "ko_status": ko_status,
        "ko_growth": json_safe_number(ko_growth),
        "rescue_status": rescue_status,
        "rescue_growth": json_safe_number(rescue_growth),
        "missing_genes": "",
        "mapped_background": "+".join(mapped_background),
        "missing_background": "+".join(missing_background),
        "mapped_rescue": "+".join(mapped_rescue),
        "missing_rescue": "+".join(missing_rescue),
        "associated_reactions": "+".join(associated_reactions),
        "bounds_after_knockout": bounds_after_knockout,
    }

    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
