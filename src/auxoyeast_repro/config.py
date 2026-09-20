from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AuditConfig:
    """Numerical and execution settings for the auxotrophy audit."""

    solver: str = "glpk"
    viability_fraction: float = 0.01
    uptake_lower_bound: float = -1000.0
    isolation_mode: str = "reload"  # reload | copy
    checkpoint_every: int = 1
    eta_window: int = 10

    def validate(self) -> None:
        if self.viability_fraction <= 0:
            raise ValueError("viability_fraction must be > 0")
        if self.uptake_lower_bound >= 0:
            raise ValueError("uptake_lower_bound must be negative")
        if self.isolation_mode not in {"reload", "copy"}:
            raise ValueError("isolation_mode must be 'reload' or 'copy'")
        if self.checkpoint_every < 1:
            raise ValueError("checkpoint_every must be >= 1")
        if self.eta_window < 1:
            raise ValueError("eta_window must be >= 1")


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    """Canonical repository paths."""

    root: Path

    @property
    def data_dir(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def output_dir(self) -> Path:
        return self.root / "results"

    @property
    def original_xml(self) -> Path:
        return self.data_dir / "yeast9.0.xml"

    @property
    def curated_xml(self) -> Path:
        return self.data_dir / "Yeast9_curated.xml"

    @property
    def dataset_xlsx(self) -> Path:
        return self.data_dir / "mmc3.xlsx"

    def required_inputs(self) -> tuple[Path, Path, Path]:
        return self.original_xml, self.curated_xml, self.dataset_xlsx

    def ensure_output_dir(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
