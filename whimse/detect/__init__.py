from collections.abc import Iterable
from dataclasses import fields
from difflib import SequenceMatcher

from whimse.config import Config
from whimse.explore.actual.types import ActualPolicy
from whimse.explore.common import LocalPolicyModifications
from whimse.explore.distributed.types import DistPolicy
from whimse.report.types import (
    BaseReport,
    DiffType,
    LocalModificationReport,
    LocalModificationReportItem,
    ReportItem,
    ReportItemLevel,
)
from whimse.selinux import Statement
from whimse.utils.logging import get_logger

_logger = get_logger(__name__)


class PolicyChangesDetector:
    def __init__(
        self, config: Config, actual_policy: ActualPolicy, dist_policy: DistPolicy
    ) -> None:
        self._config = config
        self._actual_policy = actual_policy
        self._dist_policy = dist_policy

    def _compare_set(
        self,
        field_name: str,
        actual_statements: frozenset[Statement],
        dist_statements: frozenset[Statement],
    ) -> Iterable[ReportItem]:
        for added_statement in actual_statements - dist_statements:
            yield LocalModificationReportItem(
                name=f"Addition in {field_name} local modification",
                level=ReportItemLevel.ERROR,
                diff_type=DiffType.ADDITION,
                section=field_name,
                statement=str(added_statement),
            )
        for deleted_statement in dist_statements - actual_statements:
            yield LocalModificationReportItem(
                name=f"Deletion in {field_name} local modification",
                level=ReportItemLevel.ERROR,
                diff_type=DiffType.DELETION,
                section=field_name,
                statement=str(deleted_statement),
            )

    def _list_change(
        self,
        field_name: str,
        diff_type: DiffType,
        statements: tuple[Statement],
        change_range: Iterable[int],
    ) -> Iterable[ReportItem]:
        for i in change_range:
            diff_type_str = "Addition" if diff_type == DiffType.ADDITION else "Deletion"
            yield LocalModificationReportItem(
                name=f"{diff_type_str} in {field_name} local modification with index {i}",
                level=ReportItemLevel.ERROR,
                diff_type=DiffType.ADDITION,
                section=field_name,
                statement=str(statements[i]),
            )

    def _compare_list(
        self,
        field_name: str,
        actual_statements: tuple[Statement],
        dist_statements: tuple[Statement],
    ) -> Iterable[ReportItem]:
        print("HERE", actual_statements, dist_statements)
        seq_matcher = SequenceMatcher(a=actual_statements, b=dist_statements)
        for opcode, actual1, actual2, dist1, dist2 in seq_matcher.get_opcodes():
            match opcode:
                case "equal":
                    pass
                case "delete":
                    yield from self._list_change(
                        field_name,
                        DiffType.ADDITION,
                        actual_statements,
                        range(actual1, actual2),
                    )
                case "insert":
                    yield from self._list_change(
                        field_name,
                        DiffType.DELETION,
                        dist_statements,
                        range(dist1, dist2),
                    )
                case "replace":
                    yield from self._list_change(
                        field_name,
                        DiffType.ADDITION,
                        actual_statements,
                        range(actual1, actual2),
                    )
                    yield from self._list_change(
                        field_name,
                        DiffType.DELETION,
                        dist_statements,
                        range(dist1, dist2),
                    )

    def _detect_localmod_changes(self) -> Iterable[LocalModificationReport]:
        _logger.info("Checking local policy modifications changes")
        for field in fields(LocalPolicyModifications):
            report = LocalModificationReport(field.name)
            actual_statements = getattr(
                self._actual_policy.local_modifications, field.name
            )
            dist_statements = getattr(self._dist_policy.local_modifications, field.name)
            if isinstance(actual_statements, frozenset) and isinstance(
                dist_statements, frozenset
            ):
                report.add_items(
                    self._compare_set(field.name, actual_statements, dist_statements)
                )
            elif isinstance(actual_statements, tuple) and isinstance(
                dist_statements, tuple
            ):
                report.add_items(
                    self._compare_list(field.name, actual_statements, dist_statements)
                )
            else:
                assert (
                    False
                ), f"Invalid container types {type(actual_statements)=} {type(dist_statements)=}"
            yield report

    def detect_changes(self) -> Iterable[ReportItem | BaseReport]:
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
