from logging import basicConfig, getLogger
from shutil import rmtree
from sys import stderr

from whimse.config import Config
from whimse.detect import PolicyChangesDetector
from whimse.explore import explore_stage
from whimse.report import report_formatter_factory
from whimse.report.analysis import AnalysisRunner
from whimse.report.json import JSONReportFormattter

__version__ = "1.0"


def main() -> None:
    config = Config.parse_args(__version__)
    basicConfig(level=config.log_level, stream=stderr)
    _logger = getLogger(__name__)
    for vf, level in config.log_levels.items():
        getLogger(vf).setLevel(level)
    _logger.debug("%r", config)

    explore_stage_result = explore_stage(config)

    with open("dist_policy.txt", "w") as f:
        for dist_module in explore_stage_result.dist_policy.modules:
            print(dist_module, file=f)
        print(explore_stage_result.dist_policy.local_modifications, file=f)
        print(f"{explore_stage_result.dist_policy.dontaudit_disabled=}", file=f)
    with open("actual_policy.txt", "w") as f:
        for module in explore_stage_result.actual_policy.modules:
            print(module, file=f)
        print(explore_stage_result.actual_policy.local_modifications, file=f)
        print(f"{explore_stage_result.actual_policy.dontaudit_disabled=}", file=f)

    report = Report()
    report.add_items(
        PolicyChangesDetector(
            config, explore_stage_result.actual_policy, explore_stage_result.dist_policy
        ).detect_changes()
    )

    print(report)
