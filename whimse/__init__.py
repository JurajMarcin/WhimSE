from logging import basicConfig, getLogger
from shutil import rmtree
from sys import stderr

from whimse.analyze import AnalysisRunner
from whimse.config import Config
from whimse.detect import PolicyChangesDetector
from whimse.explore import explore_policy
from whimse.report import report_formatter_factory
from whimse.report.json import JSONReportFormattter

__version__ = "0.1"


def main() -> None:
    config = Config.parse_args(__version__)
    basicConfig(level=config.log_level, stream=stderr)
    _logger = getLogger(__name__)
    for vf, level in config.log_levels.items():
        getLogger(vf).setLevel(level)
    _logger.debug("%r", config)

    try:
        if config.input:
            report = JSONReportFormattter.load_report(config.input)
        else:
            active_policy, dist_policy = explore_policy(config)
            report = PolicyChangesDetector(
                config, active_policy, dist_policy
            ).get_report()
            AnalysisRunner(config).run_analyses(report)
        report_formatter = report_formatter_factory(config, report)
        report_formatter.format_report(config.output)
    finally:
        if config.keep_work_dir:
            _logger.info("Keeping the working directory '%s'", config.work_dir)
        else:
            _logger.debug("Removing the working directory '%s", config.work_dir)
            rmtree(config.work_dir)
