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
from logging import getLogger
from typing import cast

from setools.exception import InvalidType
from setools.policyrep import SELinuxPolicy

from whimse.analyze.common import Analysis
from whimse.config import Config
from whimse.types.cildiff import (
    CilAvrule,
    CilClassperms,
    CilDiff,
    CilDiffNode,
    CilDiffSide,
    CilNode,
)
from whimse.types.reports import (
    AnalysisResult,
    AnalysisResultSection,
    Report,
)
from whimse.utils.avc import AVCEvent, get_avc_events

_logger = getLogger(__name__)


def _expand_type_names(policy: SELinuxPolicy, type_name: str) -> Iterable[str]:
    yield type_name
    try:
        type_obj = policy.lookup_type(type_name)
        yield from type_obj.aliases()
        yield from (attr.name for attr in type_obj.attributes())
    except InvalidType:
        _logger.debug("Type %r does not exist in the current policy", type_name)


class AVCMatcher:
    def __init__(self, avc: AVCEvent, policy: SELinuxPolicy) -> None:
        self._avc = avc
        self._policy = policy
        self._stypes = set(_expand_type_names(policy, avc.scontext.type))
        self._ttypes = set(_expand_type_names(policy, avc.tcontext.type))

    def _statement_filter(self, node: CilNode) -> bool:
        del node
        return True

    def _balance_diffs(self, diffs: list[CilDiff]) -> Iterable[CilDiff]:
        return diffs

    def _filter_diffs(self, diffs: Iterable[CilDiff]) -> Iterable[CilDiff]:
        yield from (diff for diff in diffs if self._statement_filter(diff.node))

    def _get_statements(
        self, diff_node: CilDiffNode
    ) -> Iterable[tuple[CilDiff, CilDiffNode]]:
        matching_diffs: list[CilDiff] = list(self._filter_diffs(diff_node.diffs))
        _logger.debug(
            "Found %d diffs matching the AVC in change of %r on line %d/%d",
            len(matching_diffs),
            diff_node.left.flavor,
            diff_node.left.line,
            diff_node.right.line,
        )
        yield from ((diff, diff_node) for diff in self._balance_diffs(matching_diffs))
        for child_node in diff_node.children:
            yield from self._get_statements(child_node)

    def get_related_diffs(
        self, diff_node: CilDiffNode
    ) -> Iterable[tuple[CilNode, CilDiff, CilDiffNode]]:
        _logger.debug(
            "Searching for related diff nodes from node with %d diffs and %d children",
            len(diff_node.diffs),
            len(diff_node.children),
        )
        return (
            (diff.node, diff, dnode) for diff, dnode in self._get_statements(diff_node)
        )

    def __str__(self) -> str:
        return (
            f"<{self.__class__.__name__} avc={self._avc} stypes={self._stypes} "
            f"ttypes={self._ttypes}>"
        )

    def __repr__(self) -> str:
        return str(self)


class AVRuleAVCMatcher(AVCMatcher):
    def _statement_filter(self, node: CilNode) -> bool:
        return (
            isinstance(node, CilAvrule)
            and (
                (self._avc.denied and node.flavor in ("allow", "deny"))
                or (not self._avc.denied and node.flavor in ("auditallow", "dontaudit"))
            )
            and node.source in self._stypes
            and node.target in self._ttypes
            and isinstance(node.classperms, CilClassperms)
            and node.classperms.cls == self._avc.tcls
            and node.classperms.perms.operator is None
            and self._avc.perms in node.classperms.perms.operands
        )

    def _causing_side(self, node: CilNode) -> CilDiffSide:
        match node.flavor:
            case "allow" | "dontaudit":
                return CilDiffSide.RIGHT
            case "deny" | "auditallow":
                return CilDiffSide.LEFT
            case _:
                raise NotImplementedError()

    def _balance_diffs(self, diffs: list[CilDiff]) -> Iterable[CilDiff]:
        _logger.debug("Balancing diffs")
        perms_sim: list[tuple[float, int, int]] = []
        balanced: set[int] = set()

        for addition_i, addition in (
            (ai, a) for ai, a in enumerate(diffs) if a.side == CilDiffSide.LEFT
        ):
            addition_classperms = cast(
                CilClassperms, cast(CilAvrule, addition.node).classperms
            )
            for deletion_i, deletion in (
                (di, d) for di, d in enumerate(diffs) if d.side == CilDiffSide.RIGHT
            ):
                if addition.node.flavor != deletion.node.flavor:
                    continue
                deletion_classperms = cast(
                    CilClassperms, cast(CilAvrule, deletion.node).classperms
                )
                add_perms = set(addition_classperms.perms.operands)
                del_perms = set(deletion_classperms.perms.operands)
                perms_sim.append(
                    (
                        len(add_perms & del_perms) / len(add_perms | del_perms),
                        addition_i,
                        deletion_i,
                    )
                )

        for _, addition_i, deletion_i in sorted(
            perms_sim, key=lambda sim: sim[0], reverse=True
        ):
            if addition_i in balanced or deletion_i in balanced:
                continue
            balanced.add(addition_i)
            balanced.add(deletion_i)

        return (
            diff
            for i, diff in enumerate(diffs)
            if diff.side == self._causing_side(diff.node) and i not in balanced
        )


class AVCAnalysis(Analysis[Report]):
    _registered_matchers: tuple[type[AVCMatcher]] = (AVRuleAVCMatcher,)

    def __init__(self, config: Config, policy: SELinuxPolicy) -> None:
        super().__init__(config, policy)
        self._matchers = [
            (avc, [matcher(avc, policy) for matcher in self._registered_matchers])
            for avc in get_avc_events(config.avc_start_time)
        ]

    def analyze(self, report: Report) -> AnalysisResult:
        _logger.info("Running AVC Analysis")
        result = AnalysisResult("AVC Analysis")
        for avc, matchers in self._matchers:
            _logger.info("Finding causes of AVC: %s", avc.text)
            _logger.debug("%r", avc)
            cause_found = False
            section = AnalysisResultSection("Possibly Caused AVC")
            section.add_item(avc.text, True)
            section.add_item(
                "The mentioned AVC denial could be possibly caused by "
                "the following policy modifications"
            )
            for matcher in matchers:
                for policy_module_report in report.policy_modules:
                    if policy_module_report.diff is None:
                        continue
                    _logger.debug(
                        "Searching report for module %r/%r with matcher %r",
                        policy_module_report.active_module,
                        policy_module_report.dist_module,
                        matcher,
                    )
                    for cil_node, diff, _ in matcher.get_related_diffs(
                        policy_module_report.diff
                    ):
                        _logger.info(
                            "Found possible cause in module %s",
                            policy_module_report.module_name,
                        )
                        cause_found = True
                        section.add_item(
                            f"{'Removal' if diff.side == CilDiffSide.RIGHT else 'Addition'} "
                            f"of the following {diff.node.flavor} statement "
                            f"on line {diff.node.line} "
                            f"in policy module {policy_module_report.module_name} "
                            f"at priority {policy_module_report.module_priority[0]}"
                            f"/{policy_module_report.module_priority[1]}"
                        )
                        section.add_item(cil_node.cil_str(), True)
            if cause_found:
                result.add_section(section)
        return result
