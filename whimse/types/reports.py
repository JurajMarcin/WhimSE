from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, Field

from whimse.types.cildiff import CilDiffNode
from whimse.types.modules import DistPolicyModule, PolicyModule


@dataclass()
class AnalysisResultItem:
    text: str
    preformat: bool = False


@dataclass()
class AnalysisResultSection:
    title: str
    items: list[AnalysisResultItem] = field(default_factory=list)

    def add_item(self, text: str, preformat: bool = False) -> AnalysisResultItem:
        item = AnalysisResultItem(text, preformat)
        self.items.append(item)
        return item


@dataclass()
class AnalysisResult:
    title: str
    sections: list[AnalysisResultSection] = field(default_factory=list)

    def add_section(
        self, title_or_section: str | AnalysisResultSection
    ) -> AnalysisResultSection:
        section = (
            title_or_section
            if isinstance(title_or_section, AnalysisResultSection)
            else AnalysisResultSection(title_or_section)
        )
        self.sections.append(section)
        return section


class BaseReport:
    pass


class ReportFormat(StrEnum):
    PLAIN = "plain"
    HTML = "html"
    JSON = "json"


class ChangeType(StrEnum):
    ADDITION = "addition"
    DELETION = "deletion"
    MODIFICATION = "modification"


@dataclass()
class DisableDontauditReport(BaseReport):
    actual_value: bool
    dist_value: bool


@dataclass()
class LocalModificationsChange:
    change_type: ChangeType
    statement: str


@dataclass()
class LocalModificationsReport(BaseReport):
    section: str
    changes: list[LocalModificationsChange] = field(default_factory=list)


class PolicyModuleReportFlag(StrEnum):
    LOOKALIKE = "lookalike"
    GENERATED = "generated"
    USING_LOCAL_POLICY = "using-local-policy"
    USING_NEWER_POLICY = "using-newer-policy"
    UNKNOWN_INSTALL_METHOD = "undetected-install-method"


@dataclass()
class PolicyModuleReport(BaseReport):
    actual_module: PolicyModule | None
    dist_module: DistPolicyModule | None
    effective: bool = False
    flags: set[PolicyModuleReportFlag] = field(default_factory=set)
    change_type: ChangeType | None = None
    diff: CilDiffNode | None = None

    @property
    def module_name(self) -> str:
        if self.actual_module:
            return self.actual_module.name
        if self.dist_module:
            return self.dist_module.module.name
        assert False, "At least actual or dist module must be not None"


class Report(BaseModel, BaseReport):
    disable_dontaudit: DisableDontauditReport
    local_modifications: list[LocalModificationsReport]
    policy_modules: list[PolicyModuleReport]
    analysis_results: list[AnalysisResult] = Field(default_factory=list)
