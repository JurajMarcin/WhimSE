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
from typing import Any, TextIO

from whimse.report.common import (
    DisableDontauditReportFormatter,
    LocalModificationsReportFormatter,
    PolicyModuleReportFormatter,
    ReportFormatter,
)

_logger = getLogger(__name__)


def _indent(string: str | Any, size: int) -> str:
    return "    " * size + str(string)


class PlainDisableDontauditReportFormatter(DisableDontauditReportFormatter):
    def formatted_lines(self) -> Iterable[str]:
        if (
            not self._config.full_report
            and self._report.active_value == self._report.dist_value
        ):
            return
        yield f"{self._title}"
        yield _indent(self._message, 1)
        yield ""


class PlainLocalModificationsReportFormatter(LocalModificationsReportFormatter):
    def formatted_lines(self) -> Iterable[str]:
        if not self._shown:
            return
        yield f"{self._title} (+{self._change_count[0]} -{self._change_count[1]})"
        for change in self._report.changes:
            yield _indent(
                f"{self._change_icon(change)}{self._change_message(change)}", 1
            )
            yield _indent(change.statement, 2)
        yield ""


class PlainPolicyModuleReportFormatter(PolicyModuleReportFormatter):
    def formatted_lines(self) -> Iterable[str]:
        if not self._shown:
            return
        yield f"{self._change_type_icon} {self._title}"
        for module_source_message in self._module_source_messages:
            yield _indent(module_source_message, 1)
        yield _indent("Active policy module files:", 1)
        yield from (_indent(file, 2) for file in self._active_module_files)
        yield _indent("Source policy module files:", 1)
        yield from (_indent(file, 2) for file in self._dist_module_files)
        if eff_msg := self._effective_message:
            yield _indent(eff_msg, 1)
        yield from (_indent(flag_msg, 1) for flag_msg in self._flag_messages)
        yield _indent(f"Changes (+{self._change_count[0]} -{self._change_count[1]})", 1)
        for diff, diff_node in self._diffs():
            yield _indent(
                f"{self._diff_side_icon(diff)} {self._diff_message(diff, diff_node)}", 1
            )
            if diff.description:
                yield _indent(diff.description, 2)
            yield from (
                _indent(cil_line, 2 + cil_indent)
                for cil_line, cil_indent in diff.node.cil()
            )
        yield ""


class PlainReportFormatter(ReportFormatter):
    def formatted_lines(self) -> Iterable[str]:
        yield self._title
        yield ""
        if self._disable_dontaudit_report:
            yield from PlainDisableDontauditReportFormatter(
                self._config, self._report.disable_dontaudit
            ).formatted_lines()
        if self._local_modifications_reports:
            yield "Local Modifications"
            yield ""
            for local_modifications_report in self._local_modifications_reports:
                yield from PlainLocalModificationsReportFormatter(
                    self._config, local_modifications_report
                ).formatted_lines()
            yield ""
        if self._policy_module_reports:
            yield "Policy Modules"
            yield ""
            for policy_module_report in self._policy_module_reports:
                yield from PlainPolicyModuleReportFormatter(
                    self._config, policy_module_report
                ).formatted_lines()
            yield ""
        if self._report.analysis_results:
            yield "Analysis Results"
            yield ""
            for analysis_result in self._report.analysis_results:
                yield analysis_result.title
                yield ""
                for analysis_result_section in analysis_result.sections:
                    yield _indent(analysis_result_section.title, 1)
                    for analysis_result_item in analysis_result_section.items:
                        yield from (
                            _indent(line, 2)
                            for line in analysis_result_item.text.splitlines()
                        )

    def format_report(self, file: TextIO) -> None:
        _logger.info("Generating plain text report")
        return super().format_report(file)
