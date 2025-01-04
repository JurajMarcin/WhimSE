from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ModuleFetchMethod(StrEnum):
    EXACT_PACKAGE = "exact_package"
    NEWER_PACKAGE = "newer_package"
    LOCAL_MODULE = "local_module"


@dataclass()
class ExploreStageConfig:
    policy_store_path: Path
    shadow_root_path: Path
    module_fetch_methods: list[ModuleFetchMethod]

    @property
    def shadow_policy_store_path(self) -> Path:
        return self.shadow_root_path / self.policy_store_path.relative_to("/")


class ExploreStageError(Exception):
    pass
