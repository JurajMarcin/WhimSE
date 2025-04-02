import logging
import shutil
from collections.abc import Iterable
from dataclasses import fields
from pathlib import Path

from whimse.config import Config, ModuleFetchMethod
from whimse.explore.common import ExploreStageError, PolicyExplorer
from whimse.explore.distribution.pm import package_manager_factory
from whimse.explore.distribution.pm.common import FetchPackageError
from whimse.types.local_modifications import LocalModifications
from whimse.types.modules import (
    DistPolicyModule,
    PolicyModule,
    PolicyModuleInstallMethod,
    PolicyModuleSource,
)
from whimse.types.policy import DistPolicy

_logger = logging.getLogger(__name__)


class DistPolicyExplorer(PolicyExplorer[DistPolicy]):
    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._package_manager = package_manager_factory(config)

    @property
    def policy_store(self) -> Path:
        return self._config.shadow_policy_store_path

    def _fetch_dist_local(
        self, modules_by_source: dict[PolicyModuleSource, set[PolicyModule]]
    ) -> Iterable[DistPolicyModule]:
        for source, source_modules in modules_by_source.items():
            if (
                not source_modules
                or source.install_method != PolicyModuleInstallMethod.SEMODULE
            ):
                continue
            for module in source_modules.copy():
                _logger.debug(
                    "Fetching files of module %r from local files",
                    module,
                )
                try:
                    for _, file in module.files:
                        target_file = self._config.shadow_root_path / file.lstrip("/")
                        target_file.parent.mkdir(exist_ok=True, parents=True)
                        shutil.copy(file, target_file)
                    yield DistPolicyModule(module, source)
                except FileNotFoundError as ex:
                    _logger.warning(
                        "Could not fetch local file %r from module %r, "
                        "will try to use another method",
                        ex.filename,
                        module,
                    )

    def _fetch_dist_package(
        self,
        fetch_method: ModuleFetchMethod,
        modules_by_source: dict[PolicyModuleSource, set[PolicyModule]],
    ) -> Iterable[DistPolicyModule]:
        for source, source_modules in modules_by_source.items():
            if not source_modules:
                continue
            _logger.debug(
                "Fetching files of modules %r from %s package",
                source_modules,
                (
                    "newer"
                    if fetch_method == ModuleFetchMethod.NEWER_PACKAGE
                    else "exact"
                ),
            )
            files = list(file for module in source_modules for _, file in module.files)
            assert files, (
                "Modules without files should have been already yielded "
                f"{source=} {source_modules=} {files=}"
            )
            try:
                fetch_package = self._package_manager.fetch_package_files(
                    source.source_package,
                    files,
                    fetch_method == ModuleFetchMethod.EXACT_PACKAGE,
                )
                yield from (
                    DistPolicyModule(module, source.with_fetch_package(fetch_package))
                    for module in source_modules
                )
            except FetchPackageError:
                pass

    def _fetch_dist_modules(
        self, dist_modules: Iterable[DistPolicyModule]
    ) -> Iterable[DistPolicyModule]:
        modules_by_source: dict[PolicyModuleSource, set[PolicyModule]] = {}
        for dist_module in dist_modules:
            if dist_module.module.files and dist_module.source.source_package:
                modules_by_source.setdefault(dist_module.source, set()).add(
                    dist_module.module
                )
            else:
                yield dist_module

        for fetch_method in self._config.module_fetch_methods:
            if fetch_method == ModuleFetchMethod.LOCAL_MODULE:
                fetched_modules = set(self._fetch_dist_local(modules_by_source))
            else:
                fetched_modules = set(
                    self._fetch_dist_package(fetch_method, modules_by_source)
                )
            for fetched_module in fetched_modules:
                modules_by_source[
                    fetched_module.source.with_fetch_package(None)
                ].remove(fetched_module.module)
                yield fetched_module

        unfetched_modules = set(
            (module, source)
            for source, source_modules in modules_by_source.items()
            for module in source_modules
        )
        if unfetched_modules:
            _logger.error("No suitable method to fetch modules %r", unfetched_modules)
            raise ExploreStageError(
                f"No suitable method to fetch modules {unfetched_modules}"
            )

    def _get_dist_modules(self) -> Iterable[DistPolicyModule]:
        return self._fetch_dist_modules(self._package_manager.find_selinux_modules())

    def get_policy(self) -> DistPolicy:
        _logger.info("Gathering facts about the distribution policy")
        _logger.debug(
            "Fetching the local modification files and the disable_dontaudit status"
        )
        self._package_manager.fetch_files(
            [
                str(self._config.policy_store_path / field.metadata["file"])
                for field in fields(LocalModifications)
            ]
            + [str(self._config.policy_store_path / "disable_dontaudit")],
            require_exact_version=False,
            notowned_ok=True,
        )
        modules = self._get_dist_modules()

        return DistPolicy(
            self.get_local_modifications(),
            self.get_disable_dontaudit_state(),
            frozenset(modules),
            self._config.shadow_root_path,
        )
