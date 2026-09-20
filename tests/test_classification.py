import numpy as np

from auxoyeast_repro.simulation import classify_auxotrophy


THRESHOLD = 0.001


def test_correct_auxotrophy():
    assert classify_auxotrophy(
        "optimal",
        0.0,
        "optimal",
        0.1,
        THRESHOLD,
    ) == "correct"


def test_type_i_when_knockout_is_viable():
    assert classify_auxotrophy(
        "optimal",
        0.01,
        "optimal",
        0.1,
        THRESHOLD,
    ) == "type_I"


def test_type_ii_when_rescue_fails():
    assert classify_auxotrophy(
        "optimal",
        0.0,
        "optimal",
        0.0,
        THRESHOLD,
    ) == "type_II"


def test_solver_error_is_not_treated_as_biological_inviability():
    assert classify_auxotrophy(
        "infeasible",
        np.nan,
        "optimal",
        0.1,
        THRESHOLD,
    ) == "solver_error"
