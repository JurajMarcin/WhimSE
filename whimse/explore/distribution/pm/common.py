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

from whimse.config import Config
from whimse.explore.common import ExploreStageError
from whimse.types.modules import DistPolicyModule, Package


class PackageManager:
    def __init__(self, config: Config) -> None:
        self._config = config

    def find_selinux_modules(self) -> Iterable[DistPolicyModule]:
        raise NotImplementedError()

    def fetch_files(
        self,
        files: list[str],
        require_exact_version: bool = True,
        notowned_ok: bool = False,
    ) -> Iterable[tuple[str, Package]]:
        del files
        del require_exact_version
        del notowned_ok
        raise NotImplementedError()

    def fetch_package_files(
        self, package: Package, files: list[str], exact_version: bool = True
    ) -> Package:
        del package
        del files
        del exact_version
        raise NotImplementedError()

    @classmethod
    def test_system(cls) -> bool:
        raise NotImplementedError()


class FetchPackageError(ExploreStageError):
    pass
