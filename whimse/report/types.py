from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, StrEnum

from whimse.explore.distributed.types import PolicyModuleSource
from whimse.selinux import PolicyModule
from whimse.utils.logging import get_logger

_logger = get_logger(__name__)


class _IndentStr:
    def _build_str(self) -> Iterable[tuple[str, int]]:
        raise NotImplementedError()

    def __str__(self) -> str:
        return "\n".join("    " * indent + line for line, indent in self._build_str())


class DiffType(StrEnum):
    NONE = "none"
    MISSING = "missing"
    EXTRA = "extra"


class ReportItemLevel(Enum):
    NOTICE = 10
    WARNING = 20
    ERROR = 30


@dataclass(frozen=True, kw_only=True)
class ReportItem:
    name: str
    level: ReportItemLevel
    diff_type: DiffType = DiffType.NONE
    description: str | None = None


@dataclass(frozen=True, kw_only=True)
class PolicyModuleReportItem(ReportItem):
    policy_module: PolicyModule
    policy_module_source: PolicyModuleSource | None = None
    policy_statements: list[str] | None = None


@dataclass(frozen=True, kw_only=True)
class LocalModificationReportItem(ReportItem):
    section: str
    statement: str


class _ReportItemCollection[ReportItemT]:
    def add_item(self, item: ReportItemT) -> None:
        del item
        raise NotImplementedError()

    def add_items(self, items: Iterable[ReportItemT]) -> None:
        for item in items:
            self.add_item(item)


class PolicyModuleReport(_ReportItemCollection[PolicyModuleReportItem], _IndentStr):
    def __init__(self) -> None:
        self._items: dict[DiffType, list[PolicyModuleReportItem]] = {}

    def add_item(self, item: PolicyModuleReportItem) -> None:
        self._items.setdefault(item.diff_type, []).append(item)

    def _build_str(self) -> Iterable[tuple[str, int]]:
        for diff_type, items in self._items.items():
            yield diff_type, 0
            yield from ((str(item), 1) for item in items)


class LocalModificationReport(
    _ReportItemCollection[LocalModificationReportItem], _IndentStr
):
    def __init__(self) -> None:
        self._items: dict[DiffType, list[LocalModificationReportItem]] = {}

    def add_item(self, item: LocalModificationReportItem) -> None:
        self._items.setdefault(item.diff_type, []).append(item)

    def _build_str(self) -> Iterable[tuple[str, int]]:
        for diff_type, items in self._items.items():
            yield diff_type, 0
            yield from ((str(item), 1) for item in items)


class Report(_ReportItemCollection[ReportItem], _IndentStr):
    def __init__(self) -> None:
        self._policy_module_reports: dict[PolicyModule, PolicyModuleReport] = {}
        self._local_modifications: dict[str, LocalModificationReport] = {}
        self._misc_items: list[ReportItem] = []

    def add_item(self, item: ReportItem) -> None:
        match item:
            case PolicyModuleReportItem():
                self._policy_module_reports.setdefault(
                    item.policy_module, PolicyModuleReport()
                ).add_item(item)
            case LocalModificationReportItem():
                self._local_modifications.setdefault(
                    item.section, LocalModificationReport()
                ).add_item(item)
            case _:
                self._misc_items.append(item)

    def _build_str(self) -> Iterable[tuple[str, int]]:
        yield "**Report**", 0
        yield from ((str(item), 1) for item in self._misc_items)
        yield "*PolicyModules*", 0
        for module, module_report in self._policy_module_reports.items():
            yield str(module), 1
            yield from ((line, 2) for line in str(module_report).splitlines())
        yield "*LocalModifications*", 0
        for local_section, local_section_report in self._local_modifications.items():
            yield str(local_section), 1
            yield from ((line, 2) for line in str(local_section_report).splitlines())
