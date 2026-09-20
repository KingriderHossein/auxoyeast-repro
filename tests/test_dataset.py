import pandas as pd

from auxoyeast_repro.dataset import parse_dataset_frame


def test_conditional_medium_is_split_into_rescue_and_background():
    frame = pd.DataFrame(
        [
            {
                "Gene Systematic Name": "YTEST1",
                "Chemical": "arginine add uracil",
                "exchange": "L-arginine exchange",
                "ID": "r_arg+r_ura",
                "Strain Background": "S288C",
                "Reference": "example",
            }
        ]
    )

    parsed = parse_dataset_frame(frame).iloc[0]

    assert parsed["rescue_ids"] == ["r_arg"]
    assert parsed["background_ids"] == ["r_ura"]
