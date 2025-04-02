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
