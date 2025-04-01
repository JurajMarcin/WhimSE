from logging import getLogger

from setools.policyrep import SELinuxPolicy

from whimse.config import Config
from whimse.report.analysis.avc import AVCAnalysis
from whimse.report.analysis.common import Analysis
from whimse.types.reports import Report

_logger = getLogger(__name__)


class AnalysisRunner:
    _registered_analyses: tuple[type[Analysis]] = (AVCAnalysis,)

    def __init__(self, config: Config) -> None:
        self._config = config
        self._policy = SELinuxPolicy()
        self._analyses = tuple(
            analysis_cls(config, self._policy)
            for analysis_cls in self._registered_analyses
        )

    def run_analyses(self, report: Report) -> None:
        _logger.info("Running analyses")
        for analysis in self._analyses:
            report.analysis_results.append(analysis.analyze(report))
