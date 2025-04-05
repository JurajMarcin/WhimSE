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

from setools.policyrep import SELinuxPolicy

from whimse.config import Config
from whimse.types.reports import AnalysisResult, BaseReport


class Analysis[ReportT: BaseReport]:
    def __init__(self, config: Config, policy: SELinuxPolicy) -> None:
        self._config = config
        self._policy = policy

    def analyze(self, report: "ReportT") -> AnalysisResult:
        del report
        raise NotImplementedError()
