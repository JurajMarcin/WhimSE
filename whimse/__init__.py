import logging
from pathlib import Path
from sys import stderr
from tempfile import mkdtemp

from whimse.config import Config, ModuleFetchMethod
from whimse.detect import PolicyChangesDetector
from whimse.explore import explore_stage
from whimse.report.types import Report
from whimse.utils.logging import get_logger

logging.basicConfig(level=logging.DEBUG, stream=stderr)


_logger = get_logger(__name__)


def main() -> None:
    _logger.debug("started")

    tmpdir = mkdtemp()
    print(tmpdir)
    config = Config(
        Path("./cildiff/src/cildiff"),
        Path("/var/lib/selinux/targeted"),
        Path(tmpdir),
        [
            ModuleFetchMethod.LOCAL_MODULE,
            ModuleFetchMethod.EXACT_PACKAGE,
            ModuleFetchMethod.NEWER_PACKAGE,
        ],
    )
    explore_stage_result = explore_stage(config)

    with open("dist_policy.txt", "w") as f:
        for module, source in explore_stage_result.dist_policy.modules.items():
            print(module, source, file=f)
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
            explore_stage_result.actual_policy, explore_stage_result.dist_policy
        ).detect_changes()
    )

    print(report)
