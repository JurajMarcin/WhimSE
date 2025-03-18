from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, StrEnum

from whimse.explore.distributed.types import DistPolicyModule
from whimse.selinux import PolicyModule
from whimse.utils.logging import get_logger

_logger = get_logger(__name__)


class _IndentStr:
    def build_str(self) -> Iterable[tuple[str, int]]:
        raise NotImplementedError()

    def __str__(self) -> str:
        return "\n".join("    " * indent + line for line, indent in self.build_str())


class DiffType(StrEnum):
    NONE = "none"
    ADDITION = "addition"
    DELETION = "deletion"


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
    statements: list[str] | None = None


@dataclass(frozen=True, kw_only=True)
class LocalModificationReportItem(ReportItem):
    section: str
    statement: str


class BaseReport[ReportItemT: ReportItem](_IndentStr):
    def __init__(self) -> None:
        self._items: list[ReportItem] = []

    def add_item(self, item: "ReportItemT") -> None:
        if not isinstance(item, ReportItem):
            raise TypeError(f"BaseReport only supports ReportItem instances, got {type(item)}")
        self._items.append(item)

    def add_items(self, items: Iterable["ReportItemT"]) -> None:
        for item in items:
            self.add_item(item)

    def build_str(self) -> Iterable[tuple[str, int]]:
        for item in self._items:
            yield str(item), 0


class PolicyModuleReport(BaseReport):
    def __init__(
        self,
        actual_module: PolicyModule | None,
        dist_module: DistPolicyModule | None,
    ) -> None:
        super().__init__()
        assert actual_module or dist_module
        self._actual_module = actual_module
        self._dist_module = dist_module

    def build_str(self) -> Iterable[tuple[str, int]]:
        yield f"{self._actual_module=} {self._dist_module=}", 0
        yield from ((line, indent + 1) for line, indent in super().build_str())


class LocalModificationReport(BaseReport):
    def __init__(self, section: str) -> None:
        super().__init__()
        self._section = section

    def build_str(self) -> Iterable[tuple[str, int]]:
        yield f"{self._section=}", 0
        yield from ((line, indent + 1) for line, indent in super().build_str())


class Report(BaseReport):
    def __init__(self) -> None:
        super().__init__()
        self._modules: list[PolicyModuleReport] = []
        self._local_modifications: list[LocalModificationReport] = []

    def add_item(self, item: ReportItem | BaseReport) -> None:
        match item:
            case PolicyModuleReport():
                self._modules.append(item)
            case LocalModificationReport():
                self._local_modifications.append(item)
            case ReportItem():
                super().add_item(item)
            case _:
                raise TypeError("Unsupported child to the root report")

    def build_str(self) -> Iterable[tuple[str, int]]:
        yield "**Report**", 0
        yield from ((line, indent + 1) for line, indent in super().build_str())
        yield "*PolicyModules*", 0
        for module_report in self._modules:
            yield from (
                (line, indent + 1) for line, indent in module_report.build_str()
            )
        yield "*LocalModifications*", 0
        for local_mod_report in self._local_modifications:
            yield from (
                (line, indent + 1) for line, indent in local_mod_report.build_str()
            )
