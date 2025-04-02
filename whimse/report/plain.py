from collections.abc import Iterable
from typing import Any

from whimse.report.common import (
    DisableDontauditReportFormatter,
    LocalModificationsReportFormatter,
    PolicyModuleReportFormatter,
    ReportFormatter,
)


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
            yield _indent(self._change_message(change), 1)
            yield _indent(change.statement, 2)
        yield ""


class PlainPolicyModuleReportFormatter(PolicyModuleReportFormatter):
    def formatted_lines(self) -> Iterable[str]:
        if not self._shown:
            return
        yield self._title
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
            yield _indent(self._diff_message(diff, diff_node), 1)
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
