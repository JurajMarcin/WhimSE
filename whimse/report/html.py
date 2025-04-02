from typing import TextIO

from jinja2 import Environment, PackageLoader

from whimse.report.common import (
    DisableDontauditReportFormatter,
    LocalModificationsReportFormatter,
    PolicyModuleReportFormatter,
    ReportFormatter,
)
from whimse.types.cildiff import CilDiff, CilDiffSide
from whimse.types.reports import ChangeType, LocalModificationsChange


class _BaseHTMLReportFormatter:
    @property
    def _added_icon(self) -> str:
        return (
            '<span class="material-symbols-outlined inline-icon green">add_box</span>'
        )

    @property
    def _modified_icon(self) -> str:
        return (
            '<span class="material-symbols-outlined inline-icon yellow">list_alt</span>'
        )

    @property
    def _deleted_icon(self) -> str:
        return (
            '<span class="material-symbols-outlined inline-icon red">'
            "indeterminate_check_box</span>"
        )


class HTMLLocalModificationsReportFormatter(
    LocalModificationsReportFormatter, _BaseHTMLReportFormatter
):

    def _change_message(self, change: LocalModificationsChange) -> str:
        match change.change_type:
            case ChangeType.ADDITION:
                return self._added_icon
            case ChangeType.DELETION:
                return self._deleted_icon
            case ChangeType.MODIFICATION:
                return self._modified_icon


class HTMLPolicyModuleReportFormatter(
    PolicyModuleReportFormatter, _BaseHTMLReportFormatter
):
    @property
    def _change_type_icon(self) -> str:
        match self._report.change_type:
            case ChangeType.ADDITION:
                return self._added_icon
            case ChangeType.DELETION:
                return self._deleted_icon
            case ChangeType.MODIFICATION:
                return self._modified_icon
            case None:
                return ""

    def _diff_side_icon(self, diff: CilDiff) -> str:
        match diff.side:
            case CilDiffSide.LEFT:
                return self._added_icon
            case CilDiffSide.RIGHT:
                return self._deleted_icon


class HTMLReportFormatter(ReportFormatter):
    def format_report(self, file: TextIO) -> None:
        template_env = Environment(loader=PackageLoader("whimse", "report/templates/"))
        template = template_env.get_template("report.html.jinja")
        html_report = template.render(
            config=self._config,
            report=self._report,
            disable_dontaudit_report=DisableDontauditReportFormatter(
                self._config, self._disable_dontaudit_report
            ),
            local_modifications_reports=[
                HTMLLocalModificationsReportFormatter(
                    self._config, local_modifications_report
                )
                for local_modifications_report in self._local_modifications_reports
            ],
            policy_module_reports=[
                HTMLPolicyModuleReportFormatter(self._config, policy_module_report)
                for policy_module_report in self._policy_module_reports
            ],
        )
        file.write(html_report)
