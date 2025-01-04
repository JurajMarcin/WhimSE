from collections.abc import Iterable
from dataclasses import fields

from whimse.explore.actual.types import ActualPolicy
from whimse.explore.common import LocalPolicyModifications
from whimse.explore.distributed.types import DistPolicy
from whimse.report.types import (
    DiffType,
    LocalModificationReportItem,
    ReportItem,
    ReportItemLevel,
)
from whimse.utils.logging import get_logger

_logger = get_logger(__name__)


class PolicyChangesDetector:
    def __init__(self, actual_policy: ActualPolicy, dist_policy: DistPolicy) -> None:
        self._actual_policy = actual_policy
        self._dist_policy = dist_policy

    def _detect_localmod_changes(self) -> Iterable[ReportItem]:
        _logger.info("Checking local policy modifications changes")
        for field in fields(LocalPolicyModifications):
            actual_statements: frozenset[str] = getattr(
                self._actual_policy.local_modifications, field.name
            )
            dist_statements: frozenset[str] = getattr(
                self._dist_policy.local_modifications, field.name
            )
            assert isinstance(actual_statements, frozenset)
            assert isinstance(dist_statements, frozenset)
            for extra_statement in actual_statements - dist_statements:
                yield LocalModificationReportItem(
                    name=f"Extra {field.name} local modification",
                    level=ReportItemLevel.ERROR,
                    diff_type=DiffType.EXTRA,
                    section=field.name,
                    statement=extra_statement,
                )
            for missing_statement in dist_statements - actual_statements:
                yield LocalModificationReportItem(
                    name=f"Missing {field.name} local modification",
                    level=ReportItemLevel.ERROR,
                    diff_type=DiffType.MISSING,
                    section=field.name,
                    statement=missing_statement,
                )

    def detect_changes(self) -> Iterable[ReportItem]:
        _logger.info("Checking changes in policy settings")
        if (
            self._actual_policy.dontaudit_disabled
            != self._dist_policy.dontaudit_disabled
        ):
            yield ReportItem(
                name="Inequal dontaudit disabled state",
                description=(
                    f"actual dontaudit disabled={self._actual_policy.dontaudit_disabled} "
                    f"distribution dontaudit disabled={self._dist_policy.dontaudit_disabled}"
                ),
                level=ReportItemLevel.ERROR,
            )

        yield from self._detect_localmod_changes()
