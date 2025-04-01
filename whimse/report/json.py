import logging
from typing import TextIO

from whimse.report.common import ReportFormatter
from whimse.types.reports import Report


class JSONReportFormattter(ReportFormatter):
    def format_report(self, file: TextIO) -> None:
        file.write(
            self._report.model_dump_json(
                indent=4 if self._config.log_level == logging.DEBUG else None,
                by_alias=True,
            )
        )

    @staticmethod
    def load_report(file: TextIO) -> Report:
        return Report.model_validate_json(file.read())
