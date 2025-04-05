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

from logging import DEBUG, getLogger
from typing import TextIO

from whimse.report.common import ReportFormatter
from whimse.types.reports import Report

_logger = getLogger(__name__)


class JSONReportFormattter(ReportFormatter):
    def format_report(self, file: TextIO) -> None:
        _logger.info("Generating JSON report")
        _logger.debug("Generating pretty formatter JSON report")
        file.write(
            self._report.model_dump_json(
                indent=4 if self._config.log_level == DEBUG else None,
                by_alias=True,
            )
        )

    @staticmethod
    def load_report(file: TextIO) -> Report:
        _logger.info("Loading JSON report")
        return Report.model_validate_json(file.read())
