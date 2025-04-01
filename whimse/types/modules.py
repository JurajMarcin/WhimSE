from dataclasses import dataclass
from enum import StrEnum


class PolicyModuleLang(StrEnum):
    CIL = "cil"
    HLL = "hll"

    @staticmethod
    def from_lang_ext(lang_ext: str) -> "PolicyModuleLang":
        match lang_ext:
            case "cil":
                return PolicyModuleLang.CIL
            case _:
                return PolicyModuleLang.HLL


@dataclass(frozen=True)
class PolicyModule:
    name: str
    priority: int
    disabled: bool
    files: frozenset[tuple[PolicyModuleLang, str]]

    def get_file(self, lang: PolicyModuleLang) -> str | None:
        for file_lang, file in self.files:
            if file_lang == lang:
                return file
        return None


@dataclass(frozen=True)
class Package:
    full_name: str
    name: str
    version: str

    def __str__(self) -> str:
        return self.full_name


class PolicyModuleInstallMethod(StrEnum):
    DIRECT = "direct"
    SEMODULE = "semodule"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PolicyModuleSource:
    install_method: PolicyModuleInstallMethod
    source_package: Package
    fetch_package: Package | None = None

    def with_fetch_package(self, fetch_package: Package) -> "PolicyModuleSource":
        return PolicyModuleSource(
            self.install_method, self.source_package, fetch_package
        )


@dataclass(frozen=True)
class DistPolicyModule:
    module: PolicyModule
    source: PolicyModuleSource
