from dataclasses import dataclass
from pathlib import Path

from whimse.types.local_modifications import LocalModifications
from whimse.types.modules import DistPolicyModule, PolicyModule


@dataclass(frozen=True)
class Policy:
    local_modifications: LocalModifications
    disable_dontaudit: bool


@dataclass(frozen=True)
class ActivePolicy(Policy):
    modules: frozenset[PolicyModule]


@dataclass(frozen=True)
class DistPolicy(Policy):
    modules: frozenset[DistPolicyModule]
    root_path: Path

    def get_file_path(self, file_path: str | Path) -> Path:
        return self.root_path / Path(file_path).relative_to("/")
