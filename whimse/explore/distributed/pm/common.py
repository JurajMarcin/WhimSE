from collections.abc import Iterable

from whimse.config import Config
from whimse.explore.distributed.types import Package, PolicyModuleSource
from whimse.explore.types import ExploreStageError
from whimse.selinux import PolicyModule
from whimse.utils.logging import get_logger

_logger = get_logger(__name__)


class PackageManager:
    def __init__(self, config: Config) -> None:
        self._config = config

    def find_selinux_modules(self) -> Iterable[tuple[PolicyModule, PolicyModuleSource]]:
        raise NotImplementedError()

    def fetch_files(
        self,
        files: list[str],
        require_exact_version: bool = True,
        notowned_ok: bool = False,
    ) -> Iterable[tuple[str, Package]]:
        del files
        del require_exact_version
        del notowned_ok
        raise NotImplementedError()

    def fetch_package_files(
        self, package: Package, files: list[str], exact_version: bool = True
    ) -> Package:
        del package
        del files
        del exact_version
        raise NotImplementedError()

    @classmethod
    def test_system(cls) -> bool:
        raise NotImplementedError()


class FetchPackageError(ExploreStageError):
    pass
