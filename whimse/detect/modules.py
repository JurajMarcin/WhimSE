# Copyright (C) 2025 Juraj Marcin <juraj@jurajmarcin.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import chain
from logging import getLogger
from pathlib import Path

from whimse.config import Config
from whimse.detect.common import ChangesDetector
from whimse.types.cildiff import CilDiffNode
from whimse.types.modules import (
    DistPolicyModule,
    PolicyModule,
    PolicyModuleInstallMethod,
    PolicyModuleLang,
)
from whimse.types.reports import (
    ChangeType,
    PolicyModuleReport,
    PolicyModuleReportFlag,
)
from whimse.utils.policy_file import read_policy_file
from whimse.utils.subprocess import run

_logger = getLogger(__name__)


def cildiff(config: Config, left_file: Path, right_file: Path) -> CilDiffNode:
    diffp = run(
        [config.cildiff_path, "--json", str(left_file), str(right_file)],
        text=True,
        logger=_logger,
        check=True,
    )
    return CilDiffNode.model_validate_json(diffp.stdout)


class ModuleComparissonException(Exception):
    pass


@dataclass()
class _PolicyModulePair:
    active_module: PolicyModule | None = None
    dist_module: DistPolicyModule | None = None
    effective_pair: bool = False


class PolicyModulesChangeDetector(ChangesDetector):
    def _get_module_pairs(self) -> Iterable[_PolicyModulePair]:
        highest_modules: dict[str, _PolicyModulePair] = {}
        active_modules_per_prio: dict[int, dict[str, PolicyModule]] = {}
        dist_modules_per_prio: dict[int, dict[str, DistPolicyModule]] = {}

        for active_module in self._active_policy.modules:
            active_modules_per_prio.setdefault(active_module.priority, {})[
                active_module.name
            ] = active_module
            if active_module.disabled:
                continue
            highest_pair = highest_modules.setdefault(
                active_module.name, _PolicyModulePair(effective_pair=True)
            )
            if (
                not highest_pair.active_module
                or highest_pair.active_module.priority < active_module.priority
            ):
                highest_pair.active_module = active_module
        for dist_module in self._dist_policy.modules:
            if dist_module.module.disabled:
                continue
            dist_modules_per_prio.setdefault(dist_module.module.priority, {})[
                dist_module.module.name
            ] = dist_module
            highest_pair = highest_modules.setdefault(
                dist_module.module.name, _PolicyModulePair(effective_pair=True)
            )
            if (
                not highest_pair.dist_module
                or highest_pair.dist_module.module.priority
                < dist_module.module.priority
            ):
                highest_pair.dist_module = dist_module

        for priority in sorted(
            set(chain(active_modules_per_prio.keys(), dist_modules_per_prio.keys()))
        ):
            for active_module in active_modules_per_prio.get(priority, {}).values():
                dist_module = dist_modules_per_prio.get(active_module.priority, {}).pop(
                    active_module.name, None
                )
                yield _PolicyModulePair(
                    active_module=active_module,
                    dist_module=dist_module,
                )
            for dist_module in dist_modules_per_prio.get(priority, {}).values():
                yield _PolicyModulePair(dist_module=dist_module)
        for highest_pair in highest_modules.values():
            if (
                highest_pair.active_module
                and highest_pair.dist_module
                and highest_pair.active_module.priority
                != highest_pair.dist_module.module.priority
            ):
                yield highest_pair

    def _get_cil_file_path(self, module: PolicyModule | None, dist: bool) -> Path:
        if not module:
            return Path("/dev/null")
        cil_path = module.get_file(PolicyModuleLang.CIL)
        if cil_path:
            return (
                Path(cil_path)
                if not dist
                else self._dist_policy.get_file_path(cil_path)
            )
        hll_path = module.get_file(PolicyModuleLang.HLL)
        assert hll_path
        cil_cache_path = self._config.cil_cache_path(hll_path, dist)
        cil_cache_path.parent.mkdir(parents=True, exist_ok=True)
        if dist:
            hll_path = self._dist_policy.get_file_path(hll_path)
        _logger.debug("Converting module %s from HLL to CIL", module.name)
        hll = read_policy_file(hll_path)
        run(
            ["/usr/libexec/selinux/hll/pp", "-", str(cil_cache_path)],
            input=hll,
            logger=_logger,
            check=True,
        )
        return cil_cache_path

    def _compare_pair(self, pair: _PolicyModulePair) -> PolicyModuleReport:
        _logger.debug("Detecting changes in policy module %r", pair)
        report = PolicyModuleReport(
            active_module=pair.active_module, dist_module=pair.dist_module
        )
        if (
            not pair.active_module
            and pair.dist_module
            and pair.dist_module.source.install_method
            == PolicyModuleInstallMethod.UNKNOWN
            and pair.dist_module.module.files
        ):
            # Files looking like policy files but no module
            report.flags.add(PolicyModuleReportFlag.LOOKALIKE)
            return report
        if (
            pair.dist_module
            and pair.dist_module.source.install_method
            == PolicyModuleInstallMethod.UNKNOWN
            and not pair.dist_module.module.files
        ):
            # Dist module with ghost files
            report.flags.add(PolicyModuleReportFlag.GENERATED)
            if not pair.active_module:
                report.change_type = ChangeType.DELETION
            return report
        if pair.dist_module:
            if not pair.dist_module.source.fetch_package:
                report.flags.add(PolicyModuleReportFlag.USING_LOCAL_POLICY)
            elif (
                pair.dist_module.source.source_package
                != pair.dist_module.source.fetch_package
            ):
                report.flags.add(PolicyModuleReportFlag.USING_NEWER_POLICY)
        if (
            pair.active_module
            and pair.dist_module
            and pair.dist_module.source.install_method
            == PolicyModuleInstallMethod.UNKNOWN
            and pair.dist_module.module.files
        ):
            # Active and dist modules with files, but undetected install method
            report.flags.add(PolicyModuleReportFlag.UNKNOWN_INSTALL_METHOD)
        # At this point both modules are either missing or have module files
        assert not pair.active_module or pair.active_module.files
        assert not pair.dist_module or pair.dist_module.module.files
        active_path = self._get_cil_file_path(pair.active_module, False)
        dist_path = self._get_cil_file_path(
            pair.dist_module.module if pair.dist_module else None, True
        )
        report.diff = cildiff(self._config, active_path, dist_path)
        report.effective = pair.effective_pair

        if not pair.active_module:
            report.change_type = ChangeType.DELETION
        elif not pair.dist_module:
            report.change_type = ChangeType.ADDITION
        elif report.diff.contains_changes:
            report.change_type = ChangeType.MODIFICATION

        return report

    def get_policy_module_reports(self) -> Iterable[PolicyModuleReport]:
        _logger.info("Detecting changes in policy modules")
        yield from (self._compare_pair(pair) for pair in self._get_module_pairs())
