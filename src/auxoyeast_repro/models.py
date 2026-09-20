from __future__ import annotations

from pathlib import Path

import cobra
import numpy as np
from cobra.io import read_sbml_model


def load_model(path: Path, solver: str):
    if solver not in cobra.util.solver.solvers:
        raise RuntimeError(
            f"Solver {solver!r} is unavailable. "
            f"Available: {sorted(cobra.util.solver.solvers)}"
        )
    model = read_sbml_model(str(path))
    model.solver = solver
    return model


def objective_reactions(model) -> list[tuple[str, float]]:
    return [
        (reaction.id, float(reaction.objective_coefficient))
        for reaction in model.reactions
        if reaction.objective_coefficient != 0
    ]


def solve_growth(model) -> tuple[str, float]:
    value = model.slim_optimize(error_value=np.nan)
    status = str(model.solver.status).lower()
    value = float(value) if value is not None else np.nan
    return status, value


def model_qc(model, label: str) -> dict:
    status, growth = solve_growth(model)
    return {
        "model": label,
        "reactions": len(model.reactions),
        "metabolites": len(model.metabolites),
        "genes": len(model.genes),
        "objective": objective_reactions(model),
        "status": status,
        "wt_growth": growth,
    }
