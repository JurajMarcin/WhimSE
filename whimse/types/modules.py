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

    def with_fetch_package(self, fetch_package: Package | None) -> "PolicyModuleSource":
        return PolicyModuleSource(
            self.install_method, self.source_package, fetch_package
        )


@dataclass(frozen=True)
class DistPolicyModule:
    module: PolicyModule
    source: PolicyModuleSource
