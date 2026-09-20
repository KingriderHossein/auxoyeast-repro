from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


REQUIRED_COLUMNS = (
    "Gene Systematic Name",
    "Chemical",
    "exchange",
    "ID",
    "Strain Background",
    "Reference",
)


def _split_plus_field(value: object) -> list[str]:
    if pd.isna(value):
        return []
    return [part.strip() for part in str(value).split("+") if part.strip()]


def _split_gene_field(value: object) -> list[str]:
    if pd.isna(value):
        return []
    return [
        part.strip()
        for part in re.split(r"\s+and\s+", str(value).strip(), flags=re.I)
        if part.strip()
    ]


def _count_exchange_targets(value: object) -> int:
    if pd.isna(value):
        return 0
    return len(
        [
            part.strip()
            for part in re.split(r"\s*\+\s*", str(value))
            if part.strip()
        ]
    )


def parse_dataset_frame(raw: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in raw.columns]
    if missing:
        raise ValueError(f"Dataset is missing required columns: {missing}")

    records: list[dict] = []
    for dataframe_index, row in raw.iterrows():
        excel_row = dataframe_index + 2
        gene_field = str(row["Gene Systematic Name"]).strip()
        chemical = str(row["Chemical"]).strip()
        exchange_field = str(row["exchange"]).strip()
        id_field = str(row["ID"]).strip()

        genes = _split_gene_field(gene_field)
        ids = _split_plus_field(id_field)
        target_count = _count_exchange_targets(exchange_field)
        conditional_medium = bool(re.search(r"\badd\b", chemical, flags=re.I))

        if not genes:
            raise ValueError(f"Excel row {excel_row}: no gene identifiers parsed")
        if not ids:
            raise ValueError(f"Excel row {excel_row}: no reaction IDs parsed")
        if target_count < 1:
            raise ValueError(f"Excel row {excel_row}: no exchange target parsed")
        if len(ids) < target_count:
            raise ValueError(
                f"Excel row {excel_row}: {target_count} exchange targets but "
                f"only {len(ids)} reaction IDs"
            )

        if conditional_medium:
            rescue_ids = ids[:target_count]
            background_ids = ids[target_count:]
            parse_rule = "target exchanges + background supplements"
        else:
            rescue_ids = ids
            background_ids = []
            parse_rule = "all IDs are rescue exchanges"

        records.append(
            {
                "pair_id": f"excel:{excel_row}",
                "excel_row": excel_row,
                "gene_field": gene_field,
                "genes": genes,
                "n_genes": len(genes),
                "chemical": chemical,
                "exchange_field": exchange_field,
                "id_field": id_field,
                "rescue_ids": rescue_ids,
                "background_ids": background_ids,
                "conditional_medium": conditional_medium,
                "parse_rule": parse_rule,
                "strain_background": str(row["Strain Background"]).strip(),
                "reference": str(row["Reference"]).strip(),
            }
        )

    parsed = pd.DataFrame(records)
    if parsed["pair_id"].duplicated().any():
        raise ValueError("pair_id values are not unique")
    return parsed


def parse_dataset(path: Path, sheet_name: str = "all") -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet_name)
    return parse_dataset_frame(raw)
