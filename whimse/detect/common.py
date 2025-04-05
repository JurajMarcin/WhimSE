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

from whimse.config import Config
from whimse.types.policy import ActivePolicy, DistPolicy


class ChangesDetector:
    def __init__(
        self, config: Config, active_policy: ActivePolicy, dist_policy: DistPolicy
    ) -> None:
        self._config = config
        self._active_policy = active_policy
        self._dist_policy = dist_policy
