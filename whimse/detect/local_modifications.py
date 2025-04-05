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

from collections.abc import Iterable
from dataclasses import fields
from difflib import SequenceMatcher
from logging import getLogger

from whimse.detect.common import ChangesDetector
from whimse.types.local_modifications import (
    LocalModifications,
    LocalModificationStatement,
)
from whimse.types.reports import (
    ChangeType,
    LocalModificationsChange,
    LocalModificationsReport,
)

_logger = getLogger(__name__)


class LocalModificationsChangesDetector(ChangesDetector):
    def _compare_set(
        self,
        active_statements: frozenset[LocalModificationStatement],
        dist_statements: frozenset[LocalModificationStatement],
    ) -> Iterable[LocalModificationsChange]:
        for added_statement in active_statements - dist_statements:
            yield LocalModificationsChange(ChangeType.ADDITION, str(added_statement))
        for deleted_statement in dist_statements - active_statements:
            yield LocalModificationsChange(ChangeType.DELETION, str(deleted_statement))

    def _list_change(
        self,
        change_type: ChangeType,
        statements: tuple[LocalModificationStatement],
        change_range: Iterable[int],
    ) -> Iterable[LocalModificationsChange]:
        for i in change_range:
            yield LocalModificationsChange(change_type, str(statements[i]))

    def _compare_list(
        self,
        active_statements: tuple[LocalModificationStatement],
        dist_statements: tuple[LocalModificationStatement],
    ) -> Iterable[LocalModificationsChange]:
        seq_matcher = SequenceMatcher(a=active_statements, b=dist_statements)
        for opcode, active1, active2, dist1, dist2 in seq_matcher.get_opcodes():
            match opcode:
                case "equal":
                    pass
                case "delete":
                    yield from self._list_change(
                        ChangeType.ADDITION,
                        active_statements,
                        range(active1, active2),
                    )
                case "insert":
                    yield from self._list_change(
                        ChangeType.DELETION,
                        dist_statements,
                        range(dist1, dist2),
                    )
                case "replace":
                    yield from self._list_change(
                        ChangeType.ADDITION,
                        active_statements,
                        range(active1, active2),
                    )
                    yield from self._list_change(
                        ChangeType.DELETION,
                        dist_statements,
                        range(dist1, dist2),
                    )

    def get_local_modifications_reports(self) -> Iterable[LocalModificationsReport]:
        _logger.info("Detecting changes in local modifications")
        for field in fields(LocalModifications):
            _logger.debug(
                "Detecting changes in %s local modifications (%r)",
                field.name,
                field.metadata["file"],
            )
            report = LocalModificationsReport(field.metadata["file"])
            active_statements = getattr(
                self._active_policy.local_modifications, field.name
            )
            dist_statements = getattr(self._dist_policy.local_modifications, field.name)
            if isinstance(active_statements, frozenset) and isinstance(
                dist_statements, frozenset
            ):
                report.changes.extend(
                    self._compare_set(active_statements, dist_statements)
                )
            elif isinstance(active_statements, tuple) and isinstance(
                dist_statements, tuple
            ):
                report.changes.extend(
                    self._compare_list(active_statements, dist_statements)
                )
            else:
                assert (
                    False
                ), f"Invalid container types {type(active_statements)=} {type(dist_statements)=}"
            yield report
