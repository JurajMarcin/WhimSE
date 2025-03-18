from collections.abc import Iterable
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

from whimse.config import Config
from whimse.detect.modules.cildiff import cildiff
from whimse.explore.actual.types import ActualPolicy
from whimse.explore.distributed.types import (
    DistPolicy,
    DistPolicyModule,
    PolicyModuleInstallMethod,
)
from whimse.report.types import (
    DiffType,
    PolicyModuleReport,
    PolicyModuleReportItem,
    ReportItem as ReportItem,
    ReportItemLevel,
)
from whimse.selinux import PolicyModule, PolicyModuleLang
from whimse.utils.policy_file import read_policy_file
from whimse.utils.logging import get_logger
from whimse.utils.subprocess import run

_logger = get_logger(__name__)


class ModuleComparissonException(Exception):
    pass


@dataclass()
class PolicyModulePair:
    actual_module: PolicyModule | None = None
    dist_module: DistPolicyModule | None = None
    effective_pair: bool = False


class PolicyModulesChangeDetector:
    def __init__(
        self, config: Config, actual_policy: ActualPolicy, dist_policy: DistPolicy
    ) -> None:
        self._config = config
        self._actual_policy = actual_policy
        self._dist_policy = dist_policy

    def _get_module_pairs(self) -> Iterable[PolicyModulePair]:
        highest_modules: dict[str, PolicyModulePair] = {}
        actual_modules_per_prio: dict[int, dict[str, PolicyModule]] = {}
        dist_modules_per_prio: dict[int, dict[str, DistPolicyModule]] = {}

        for actual_module in self._actual_policy.modules:
            actual_modules_per_prio.setdefault(actual_module.priority, {})[
                actual_module.name
            ] = actual_module
            if actual_module.disabled:
                continue
            highest_pair = highest_modules.setdefault(
                actual_module.name, PolicyModulePair(effective_pair=True)
            )
            if (
                highest_pair.actual_module is None
                or highest_pair.actual_module.priority < actual_module.priority
            ):
                highest_pair.actual_module = actual_module
        for dist_module in self._dist_policy.modules:
            if dist_module.module.disabled:
                continue
            dist_modules_per_prio.setdefault(dist_module.module.priority, {})[
                dist_module.module.name
            ] = dist_module
            highest_pair = highest_modules.setdefault(
                dist_module.module.name, PolicyModulePair(effective_pair=True)
            )
            if (
                highest_pair.dist_module is None
                or highest_pair.dist_module.module.priority
                < dist_module.module.priority
            ):
                highest_pair.dist_module = dist_module

        for highest_pair in highest_modules.values():
            if highest_pair.actual_module:
                actual_modules_per_prio[highest_pair.actual_module.priority].pop(
                    highest_pair.actual_module.name
                )
            if highest_pair.dist_module:
                dist_modules_per_prio[highest_pair.dist_module.module.priority].pop(
                    highest_pair.dist_module.module.name
                )
            yield highest_pair

        for priority in sorted(
            set(chain(actual_modules_per_prio.keys(), dist_modules_per_prio.keys()))
        ):
            for actual_module in actual_modules_per_prio.get(priority, {}).values():
                dist_module = dist_modules_per_prio.get(actual_module.priority, {}).pop(
                    actual_module.name, None
                )
                yield PolicyModulePair(
                    actual_module=actual_module,
                    dist_module=dist_module,
                )
            for dist_module in dist_modules_per_prio.get(priority, {}).values():
                yield PolicyModulePair(dist_module=dist_module)

    def _get_cil_file_path(self, module: PolicyModule | None, dist: bool) -> Path:
        if module is None:
            return Path("/dev/null")
        cil_path = module.get_file(PolicyModuleLang.CIL)
        if cil_path is not None:
            return (
                Path(cil_path)
                if not dist
                else self._dist_policy.get_file_path(cil_path)
            )
        hll_path = module.get_file(PolicyModuleLang.HLL)
        assert hll_path is not None
        cil_cache_path = self._config.cil_cache_path(hll_path, dist)
        cil_cache_path.parent.mkdir(parents=True, exist_ok=True)
        if dist:
            hll_path = self._dist_policy.get_file_path(hll_path)
        _logger.info("Converting module %s from HLL to CIL", module.name)
        hll = read_policy_file(hll_path)
        run(
            ["/usr/libexec/selinux/hll/pp", "-", str(cil_cache_path)],
            input=hll,
            logger=_logger,
            check=True,
        )
        return cil_cache_path

    def _compare_pair(self, pair: PolicyModulePair) -> PolicyModuleReport:
        report = PolicyModuleReport(pair.actual_module, pair.dist_module)
        if (
            pair.actual_module is None
            and pair.dist_module is not None
            and pair.dist_module.source.install_method
            == PolicyModuleInstallMethod.UNKNOWN
            and len(pair.dist_module.module.files) > 0
        ):
            # Files looking like policy files but no module
            report.add_item(
                PolicyModuleReportItem(
                    name="Unknown files found", level=ReportItemLevel.NOTICE
                )
            )
            return report
        if (
            pair.dist_module is not None
            and pair.dist_module.source.install_method
            == PolicyModuleInstallMethod.UNKNOWN
            and len(pair.dist_module.module.files) == 0
        ):
            # Dist module with ghost files
            report.add_item(
                PolicyModuleReportItem(
                    name="Generated module", level=ReportItemLevel.WARNING
                )
            )
            if not pair.actual_module:
                report.add_item(
                    PolicyModuleReportItem(
                        name="Deleted generated module",
                        level=ReportItemLevel.ERROR,
                        diff_type=DiffType.DELETION,
                    )
                )
            return report
        if pair.dist_module is not None:
            if pair.dist_module.source.fetch_package is None:
                report.add_item(
                    PolicyModuleReportItem(
                        name="Using the second local copy as the distribution policy module",
                        level=ReportItemLevel.WARNING,
                    )
                )
            elif (
                pair.dist_module.source.source_package
                != pair.dist_module.source.fetch_package
            ):
                report.add_item(
                    PolicyModuleReportItem(
                        name="The version of the installed package and the fetched package do not match",
                        level=ReportItemLevel.WARNING,
                    )
                )
        if (
            pair.actual_module is not None
            and pair.dist_module is not None
            and pair.dist_module.source.install_method
            == PolicyModuleInstallMethod.UNKNOWN
            and len(pair.dist_module.module.files) > 0
        ):
            report.add_item(
                PolicyModuleReportItem(
                    name="Undetected install method",
                    level=ReportItemLevel.WARNING,
                    description="This files might not be the correct policy module",
                )
            )
        assert (pair.actual_module is None or len(pair.actual_module.files) > 0) and (
            pair.dist_module is None or len(pair.dist_module.module.files) > 0
        )
        actual_path = self._get_cil_file_path(pair.actual_module, False)
        dist_path = self._get_cil_file_path(
            pair.dist_module.module if pair.dist_module else None, True
        )

        root_diff = cildiff(self._config, actual_path, dist_path)


        report.add_item(
            PolicyModuleReportItem(
                name=f"Comparing {actual_path=} {dist_path=}",
                level=ReportItemLevel.NOTICE,
                description=repr(root_diff),
            )
        )

        return report

    def detect_changes(self) -> Iterable[PolicyModuleReport]:
        yield from (self._compare_pair(pair) for pair in self._get_module_pairs())
