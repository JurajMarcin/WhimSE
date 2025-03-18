from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ModuleFetchMethod(StrEnum):
    EXACT_PACKAGE = "exact_package"
    NEWER_PACKAGE = "newer_package"
    LOCAL_MODULE = "local_module"


@dataclass()
class Config:
    cildiff_path: Path
    policy_store_path: Path
    working_directory: Path
    module_fetch_methods: list[ModuleFetchMethod]

    @property
    def shadow_root_path(self) -> Path:
        return self.working_directory / "root"

    @property
    def shadow_policy_store_path(self) -> Path:
        return self.shadow_root_path / self.policy_store_path.relative_to("/")

    def cil_cache_path(self, path: str | Path, dist: bool = False) -> Path:
        return (
            self.working_directory
            / "cilcache"
            / ("actual" if not dist else "dist")
            / Path(path).relative_to("/")
        )
