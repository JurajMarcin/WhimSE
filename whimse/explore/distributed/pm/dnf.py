import re
import shlex
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from rpm import (  # pylint: disable=no-name-in-module
    RPMDBI_INSTFILENAMES,  # pyright: ignore[reportAttributeAccessIssue]
    RPMFILE_GHOST,  # pyright: ignore[reportAttributeAccessIssue]
    RPMTAG_EVR,  # pyright: ignore[reportAttributeAccessIssue]
    RPMTAG_FILEFLAGS,  # pyright: ignore[reportAttributeAccessIssue]
    RPMTAG_FILENAMES,  # pyright: ignore[reportAttributeAccessIssue]
    RPMTAG_NAME,  # pyright: ignore[reportAttributeAccessIssue]
    RPMTAG_NEVRA,  # pyright: ignore[reportAttributeAccessIssue]
    RPMTAG_POSTIN,  # pyright: ignore[reportAttributeAccessIssue]
    RPMTAG_POSTINPROG,  # pyright: ignore[reportAttributeAccessIssue]
    RPMVSF_MASK_NOSIGNATURES,  # pyright: ignore[reportAttributeAccessIssue]
    rpm,
)

from whimse.explore.distributed.pm.common import FetchPackageError, PackageManager
from whimse.explore.distributed.types import (
    Package,
    PolicyModuleInstallMethod,
    PolicyModuleSource,
)
from whimse.explore.types import ExploreStageConfig
from whimse.selinux import PolicyModule, PolicyModuleLang
from whimse.utils.logging import get_logger
from whimse.utils.semodule import list_semodule_installs
from whimse.utils.subprocess import run

_logger = get_logger(__name__)

PROVIDED_MODULE_PATTERN = re.compile(
    r"(?P<module_name>[^\/]+)\.(?P<lang_ext>pp|cil)(?:\.(?P<file_compression>\w+))?$"
)


@dataclass()
class _PackageModules:
    direct: set[PolicyModule] = field(default_factory=set)
    installed: set[PolicyModule] = field(default_factory=set)
    ghost: dict[str, set[int]] = field(default_factory=dict)
    provided_files: dict[str, tuple[str, str]] = field(default_factory=dict)


class DNFPackageManager(PackageManager):
    @classmethod
    def test_system(cls) -> bool:
        rpm_process = run(["rpm", "--version"], check=False, logger=_logger)
        dnf_process = run(["dnf", "--version"], check=False, logger=_logger)
        return rpm_process.returncode == 0 and dnf_process.returncode == 0

    def __init__(self, explore_config: ExploreStageConfig) -> None:
        super().__init__(explore_config)
        self._store_module_pattern = re.compile(
            rf"^{re.escape(str(explore_config.policy_store_path).rstrip('/'))}"
            rf"\/active\/modules\/(?P<priority>\d+)\/(?P<module_name>[^\/]+)$"
        )
        self._rpms_cache_path = self._explore_config.shadow_root_path / ".rpms"

    def _rpm_package_to_package(self, rpm_package) -> Package:
        return Package(
            rpm_package[RPMTAG_NEVRA],
            rpm_package[RPMTAG_NAME],
            rpm_package[RPMTAG_EVR],
        )

    def _find_package_modules(
        self, package: Package, package_files: dict[str, int]
    ) -> _PackageModules:
        package_modules = _PackageModules()
        _logger.debug("Searching for policy modules in package %r", package.full_name)

        for file, flags in package_files.items():
            if match := self._store_module_pattern.match(file):
                name = match.group("module_name")
                priority = int(match.group("priority"))
                # Package contains module directory in policy store
                if flags & RPMFILE_GHOST:
                    # Module directory is only in package metadata, possibly
                    # the module is installed later from one of the provided
                    # module files
                    _logger.verbose(
                        "Found ghost module %r with priority %r in package %r",
                        name,
                        priority,
                        package,
                    )
                    package_modules.ghost.setdefault(name, set()).add(priority)
                elif f"{file}/lang_ext" in package_files and not (
                    package_files[f"{file}/lang_ext"] & RPMFILE_GHOST
                ):
                    # Module directory contains module files
                    module_files: list[tuple[PolicyModuleLang, str]] = []
                    disabled_file = str(
                        self._explore_config.policy_store_path
                        / "active/modules/disabled"
                        / name
                    )
                    if f"{file}/cil" in package_files and not (
                        package_files[f"{file}/cil"] & RPMFILE_GHOST
                    ):
                        module_files.append((PolicyModuleLang.CIL, f"{file}/cil"))
                    if f"{file}/hll" in package_files and not (
                        package_files[f"{file}/cil"] & RPMFILE_GHOST
                    ):
                        module_files.append((PolicyModuleLang.HLL, f"{file}/hll"))
                    if module_files:
                        module = PolicyModule(
                            name,
                            priority,
                            disabled_file in package_files,
                            frozenset(module_files),
                        )
                        _logger.verbose(
                            "Found direct module %r in package %r", module, package
                        )
                        package_modules.direct.add(module)
                    else:
                        _logger.warning(
                            "Direct module %r in package %r does not have required module files",
                            (name, priority),
                            package,
                        )
            elif match := PROVIDED_MODULE_PATTERN.search(file):
                # File is not in policy store, but it looks like a policy
                # module file that could be installed later
                module_name, lang_ext = match.group("module_name", "lang_ext")
                _logger.verbose(
                    "Found possible provided module file %r in package %r",
                    file,
                    package,
                )
                package_modules.provided_files[file] = (module_name, lang_ext)

        return package_modules

    def _find_installed_modules(
        self,
        post_install: str,
        package_modules: _PackageModules,
        package: Package,
    ) -> _PackageModules:
        _logger.debug(
            "Searching for installed policy modules in package %r", package.full_name
        )
        for install_file, install_priority in list_semodule_installs(post_install):
            _logger.verbose(
                "Found install of %r as policy module with priority %r in package %r",
                install_file,
                install_priority,
                package,
            )
            if install_file in package_modules.provided_files:
                name, lang_ext = package_modules.provided_files.pop(install_file)
                module_files = {
                    (PolicyModuleLang.from_lang_ext(lang_ext), install_file)
                }
            else:
                _logger.warning(
                    "File %r installed with package %s has not been found in the package files",
                    install_file,
                    package.full_name,
                )
                install_file_match = PROVIDED_MODULE_PATTERN.search(install_file)
                if install_file_match is None:
                    _logger.warning(
                        "File %r installed with package %r has invalid language extension",
                        install_file,
                        package.full_name,
                    )
                    continue
                name = install_file_match.group("module_name")
                module_files = set()
            if name in package_modules.ghost:
                if install_priority not in package_modules.ghost[name]:
                    _logger.warning(
                        "File %r installed with package %r is installed with different priority "
                        "than in ghosted module",
                        install_file,
                        package.full_name,
                    )
                else:
                    package_modules.ghost[name].remove(install_priority)
                    if not package_modules.ghost[name]:
                        package_modules.ghost.pop(name)
            package_modules.installed.add(
                PolicyModule(name, install_priority, False, frozenset(module_files))
            )

        return package_modules

    def find_selinux_modules(self) -> Iterable[tuple[PolicyModule, PolicyModuleSource]]:
        ts = rpm.TransactionSet()
        for rpm_package in ts.dbMatch():
            package = self._rpm_package_to_package(rpm_package)
            package_files = dict(
                zip(rpm_package[RPMTAG_FILENAMES], rpm_package[RPMTAG_FILEFLAGS])
            )
            package_modules = self._find_package_modules(package, package_files)
            if (
                rpm_package[RPMTAG_POSTIN] is not None
                and rpm_package[RPMTAG_POSTINPROG]
                and rpm_package[RPMTAG_POSTINPROG][0].split("/")[-1]
                in ("sh", "bash", "zsh")
            ):
                package_modules = self._find_installed_modules(
                    rpm_package[RPMTAG_POSTIN], package_modules, package
                )
            yield from (
                (module, PolicyModuleSource(PolicyModuleInstallMethod.DIRECT, package))
                for module in package_modules.direct
            )
            yield from (
                (
                    module,
                    PolicyModuleSource(PolicyModuleInstallMethod.SEMODULE, package),
                )
                for module in package_modules.installed
            )
            if package_modules.ghost:
                _logger.warning(
                    "Package %r contains modules whose install has not been detected or installed "
                    "file has not been found in package files",
                    package.name,
                )
                yield from (
                    (
                        PolicyModule(name, priority, False, frozenset()),
                        PolicyModuleSource(
                            PolicyModuleInstallMethod.UNKNOWN,
                            package,
                        ),
                    )
                    for name, priorities in package_modules.ghost.items()
                    for priority in priorities
                )
            if package_modules.provided_files:
                _logger.warning(
                    "Package %r contains possible module files whose install has not been detected",
                    package.name,
                )
                yield from (
                    (
                        PolicyModule(
                            name,
                            -1,
                            False,
                            frozenset(
                                {(PolicyModuleLang.from_lang_ext(lang_ext), file)}
                            ),
                        ),
                        PolicyModuleSource(
                            PolicyModuleInstallMethod.UNKNOWN,
                            package,
                        ),
                    )
                    for file, (name, lang_ext) in package_modules.provided_files.items()
                )

    def fetch_files(
        self,
        files: list[str],
        require_exact_version: bool = True,
        notowned_ok: bool = False,
    ) -> Iterable[tuple[str, Package]]:
        files_by_package: dict[Package, list[str]] = {}
        for file in files:
            ts = rpm.TransactionSet()
            try:
                rpm_package = next(ts.dbMatch(RPMDBI_INSTFILENAMES, file))
            except StopIteration:
                if notowned_ok:
                    continue
                raise FetchPackageError(f"No package provides file '{file}'") from None
            package = self._rpm_package_to_package(rpm_package)
            files_by_package.setdefault(package, []).append(file)

        for package, package_files in files_by_package.items():
            try:
                fetch_package = self.fetch_package_files(package, package_files, True)
            except FetchPackageError:
                if require_exact_version:
                    raise
                fetch_package = self.fetch_package_files(package, package_files, False)
            yield from ((file, fetch_package) for file in package_files)

    def _get_cached_rpm(self, package: Package, exact_version: bool) -> Path:
        if exact_version:
            try:
                return next(self._rpms_cache_path.glob(f"{package.full_name}*.rpm"))
            except StopIteration:
                if epoch_match := re.match(r"^(?P<epoch>\d+:)\d.*$", package.version):
                    return next(
                        self._rpms_cache_path.glob(
                            f"{package.full_name.replace(epoch_match.group("epoch"), "", 1)}*.rpm"
                        ),
                    )
        return next(self._rpms_cache_path.glob(f"{package.name}*.rpm"))

    def fetch_package_files(
        self, package: Package, files: list[str], exact_version: bool = True
    ) -> Package:
        assert files, f"There should be at least one file to fetch {package=}"
        package_name = package.full_name if exact_version else package.name
        try:
            rpm_path = self._get_cached_rpm(package, exact_version)
        except StopIteration:
            self._rpms_cache_path.mkdir(parents=True, exist_ok=True)
            dnf_process = run(
                ["dnf", "download", package_name],
                cwd=self._rpms_cache_path,
                check=False,
                logger=_logger,
            )
            if dnf_process.returncode != 0:
                raise FetchPackageError(
                    f"Could not fetch package {package_name}"
                ) from None
            rpm_path = self._get_cached_rpm(package, exact_version)

        with open(rpm_path, "rb") as rpm_handle:
            ts = rpm.TransactionSet(vsflags=RPMVSF_MASK_NOSIGNATURES)
            rpm_package = ts.hdrFromFdno(rpm_handle.fileno())
            package = self._rpm_package_to_package(rpm_package)

        files_list = list(f".{file}" for file in files)
        _logger.debug(
            "Extracting files %r from package %r", files_list, package.full_name
        )
        run(
            f"rpm2cpio {rpm_path} | cpio -imd {shlex.join(files_list)}",
            cwd=self._explore_config.shadow_root_path,
            shell=True,
            check=True,
            logger=_logger,
        )

        return package
