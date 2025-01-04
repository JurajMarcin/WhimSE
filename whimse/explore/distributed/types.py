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
