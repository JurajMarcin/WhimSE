from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from whimse.explore.common import LocalPolicyModifications
from whimse.selinux import PolicyModule


@dataclass(frozen=True)
class Package:
    full_name: str
    name: str
    version: str

    def __str__(self) -> str:
        return self.full_name


class PolicyModuleInstallMethod(Enum):
    DIRECT = "direct"
    SEMODULE = "semodule"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PolicyModuleSource:
    install_method: PolicyModuleInstallMethod
    source_package: Package
    fetch_package: Package | None = None

    def with_fetch_package(self, fetch_package: Package) -> "PolicyModuleSource":
        return PolicyModuleSource(
            self.install_method, self.source_package, fetch_package
        )


@dataclass(frozen=True)
class DistPolicyModule:
    module: PolicyModule
    source: PolicyModuleSource


@dataclass(frozen=True)
class DistPolicy:
    modules: frozenset[DistPolicyModule]
    local_modifications: LocalPolicyModifications
    dontaudit_disabled: bool

    root_path: Path

    def get_file_path(self, file_path: str | Path) -> Path:
        return self.root_path / Path(file_path).relative_to("/")
