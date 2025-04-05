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
from pathlib import Path

from whimse.types.local_modifications import LocalModifications
from whimse.types.modules import DistPolicyModule, PolicyModule


@dataclass(frozen=True)
class Policy:
    local_modifications: LocalModifications
    disable_dontaudit: bool


@dataclass(frozen=True)
class ActivePolicy(Policy):
    modules: frozenset[PolicyModule]


@dataclass(frozen=True)
class DistPolicy(Policy):
    modules: frozenset[DistPolicyModule]
    root_path: Path

    def get_file_path(self, file_path: str | Path) -> Path:
        return self.root_path / Path(file_path).relative_to("/")
