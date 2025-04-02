from logging import getLogger

from whimse.config import Config
from whimse.explore.distribution.pm.common import PackageManager
from whimse.explore.distribution.pm.dnf import DNFPackageManager

_logger = getLogger(__name__)

_PACKAGE_MANAGER_CLASSES = [DNFPackageManager]


def package_manager_factory(config: Config) -> PackageManager:
    _logger.debug("Finding system package manager")
    for pm_class in _PACKAGE_MANAGER_CLASSES:
        if pm_class.test_system():
            return pm_class(config)
    raise NotImplementedError("No supported package manager has been found")
