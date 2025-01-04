from whimse.explore.distributed.pm.common import PackageManager
from whimse.explore.distributed.pm.dnf import DNFPackageManager
from whimse.explore.types import ExploreStageConfig
from whimse.utils.logging import get_logger

_logger = get_logger(__name__)

_PACKAGE_MANAGER_CLASSES = [DNFPackageManager]


def system_package_manager_factory(
    explore_config: ExploreStageConfig,
) -> PackageManager:
    for pm_class in _PACKAGE_MANAGER_CLASSES:
        if pm_class.test_system():
            return pm_class(explore_config)
    raise NotImplementedError("No supported package manager has been found")
