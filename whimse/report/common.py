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
from logging import getLogger
from typing import TextIO

from whimse.config import Config
from whimse.types.cildiff import CilDiff, CilDiffNode, CilDiffSide
from whimse.types.reports import (
    BaseReport,
    ChangeType,
    DisableDontauditReport,
    LocalModificationsChange,
    LocalModificationsReport,
    PolicyModuleReport,
    PolicyModuleReportFlag,
    Report,
)
from whimse.utils import either

_logger = getLogger(__name__)


class BaseReportFormatter[ReportT: BaseReport]:
    def __init__(self, config: Config, report: "ReportT") -> None:
        self._config = config
        self._report = report

    def formatted_lines(self) -> Iterable[str]:
        return ()

    def format_report(self, file: TextIO) -> None:
        _logger.debug("Formatting the report using formatted_lines from %r", self)
        file.writelines(line + "\n" for line in self.formatted_lines())

    def _count_changes(
        self, change_types: Iterable[ChangeType]
    ) -> tuple[int, int, int]:
        additions, deletions, modifications = 0, 0, 0
        for change_type in change_types:
            match change_type:
                case ChangeType.ADDITION:
                    additions += 1
                case ChangeType.DELETION:
                    deletions += 1
                case ChangeType.MODIFICATION:
                    modifications += 1
        return additions, deletions, modifications


class DisableDontauditReportFormatter(BaseReportFormatter[DisableDontauditReport]):
    @property
    def _shown(self) -> bool:
        return (
            self._config.full_report
            or self._report.active_value != self._report.dist_value
        )

    @property
    def _title(self) -> str:
        return "Disable dontaudit"

    _setting_str = {True: "disabled", False: "enabled"}

    @property
    def _message(self) -> str:
        if self._report.active_value != self._report.dist_value:
            return (
                f"Disable dontaudit settings do not match "
                f"active=dontaudit {self._setting_str[self._report.active_value]} "
                f"distribution=dontaudit {self._setting_str[self._report.dist_value]}."
            )
        return "Disable dontaudit setting is unchanged."


class LocalModificationsReportFormatter(BaseReportFormatter[LocalModificationsReport]):
    def __init__(self, config: Config, report: LocalModificationsReport) -> None:
        super().__init__(config, report)
        self._change_count_cache: tuple[int, int] | None = None

    @property
    def _shown(self) -> bool:
        return bool(self._config.full_report or self._report.changes)

    @property
    def _change_count(self) -> tuple[int, int]:
        if not self._change_count_cache:
            self._change_count_cache = self._count_changes(
                change.change_type for change in self._report.changes
            )[0:2]
        return self._change_count_cache

    @property
    def _title(self) -> str:
        return f"{self._report.section}"

    def _change_icon(self, change: LocalModificationsChange) -> str:
        del change
        return ""

    def _change_message(self, change: LocalModificationsChange) -> str:
        return f"{change.change_type.capitalize()}"


class PolicyModuleReportFormatter(BaseReportFormatter[PolicyModuleReport]):
    def __init__(self, config: Config, report: PolicyModuleReport) -> None:
        super().__init__(config, report)
        self._changes_count_cache: tuple[int, int] | None = None

    @property
    def _shown(self) -> bool:
        return bool(
            (
                self._config.full_report
                or self._report.flags
                or self._report.change_type
                or (self._report.diff and self._report.diff.contains_changes)
            )
            and (
                self._config.show_lookalikes
                or PolicyModuleReportFlag.LOOKALIKE not in self._report.flags
            )
        )

    @property
    def _id(self) -> str:
        return (
            f"{self._report.module_name}"
            f"@{self._report.module_priority[0]}-{self._report.module_priority[1]}"
        )

    @property
    def _change_type_icon(self) -> str:
        match self._report.change_type:
            case ChangeType.ADDITION:
                return "(+)"
            case ChangeType.DELETION:
                return "(-)"
            case ChangeType.MODIFICATION:
                return "(.)"
            case None:
                return "   "

    @property
    def _title(self) -> str:
        title = f"{self._report.module_name} at "
        if self._report.module_priority[0] == self._report.module_priority[1]:
            return f"{title} {either(self._report.module_priority)}"
        return f"{title} {self._report.module_priority[0]}/{self._report.module_priority[1]}"

    @property
    def _module_source_messages(self) -> Iterable[str]:
        if not self._report.dist_module:
            yield "No package found for the policy module."
            return
        yield f"Installed package: {self._report.dist_module.source.source_package}"
        if self._report.dist_module.source.fetch_package:
            yield f"Fetched package: {self._report.dist_module.source.fetch_package}"

    @property
    def _active_module_files(self) -> Iterable[str]:
        if not self._report.active_module:
            return ()
        return (file for _, file in self._report.active_module.files)

    @property
    def _dist_module_files(self) -> Iterable[str]:
        if not self._report.dist_module:
            return ()
        return (file for _, file in self._report.dist_module.module.files)

    @property
    def _effective_message(self) -> str | None:
        return (
            "This policy module comparison has been made between modules at the highest available "
            "priority to get the effective differences between active and distribution policies."
            if self._report.effective
            else None
        )

    @property
    def _flag_messages(self) -> Iterable[str]:
        for flag in self._report.flags:
            match flag:
                case PolicyModuleReportFlag.LOOKALIKE:
                    yield (
                        "This file looks like it could be policy file, "
                        "but has not been found in the policy."
                    )
                case PolicyModuleReportFlag.GENERATED:
                    yield (
                        "Installation source of this module could not be found, "
                        "it is possible this module is generated during package installation."
                    )
                case PolicyModuleReportFlag.USING_LOCAL_POLICY:
                    yield (
                        "Using second local copy (semodule installation source) "
                        "for module comparison."
                    )
                case PolicyModuleReportFlag.USING_NEWER_POLICY:
                    yield "Using policy module from newer package version than installed."
                case PolicyModuleReportFlag.UNKNOWN_INSTALL_METHOD:
                    yield "Could not detect installation method."

    @property
    def _change_count(self) -> tuple[int, int]:
        if not self._changes_count_cache:
            self._changes_count_cache = self._count_changes(
                (
                    ChangeType.ADDITION
                    if diff.side == CilDiffSide.LEFT
                    else ChangeType.DELETION
                )
                for diff, _ in self._diffs()
            )[0:2]
        return self._changes_count_cache

    def _diffs(
        self, diff_node: CilDiffNode | None = None
    ) -> Iterable[tuple[CilDiff, CilDiffNode]]:
        if not diff_node:
            diff_node = self._report.diff
            if not diff_node:
                return
        yield from ((diff, diff_node) for diff in diff_node.diffs)
        for child_node in diff_node.children:
            yield from self._diffs(child_node)

    def _diff_side_icon(self, diff: CilDiff) -> str:
        match diff.side:
            case CilDiffSide.LEFT:
                return "Added"
            case CilDiffSide.RIGHT:
                return "Deleted"

    def _diff_message(self, diff: CilDiff, diff_node: CilDiffNode) -> str:
        node_message = "."
        if diff_node.left.flavor:
            node_message = (
                f" in {diff_node.left.flavor} statement "
                f"on line {diff_node.left.line} (active) / {diff_node.right.line} (distribution)."
            )
        return (
            f"{diff.node.flavor} statement " f"on line {diff.node.line}{node_message}"
        )


class ReportFormatter(BaseReportFormatter[Report]):
    @property
    def _title(self) -> str:
        return "What Have I Modified in SELinux"

    @property
    def _disable_dontaudit_report(self) -> DisableDontauditReport:
        return self._report.disable_dontaudit

    @property
    def _local_modifications_reports(self) -> list[LocalModificationsReport]:
        return self._report.local_modifications

    @property
    def _policy_module_reports(self) -> list[PolicyModuleReport]:
        return sorted(
            self._report.policy_modules,
            key=lambda pmr: (
                pmr.module_name,
                *(prio if prio else -1 for prio in pmr.module_priority),
            ),
        )
