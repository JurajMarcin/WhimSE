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

from collections.abc import Callable, Iterable
from dataclasses import fields
from logging import getLogger
from pathlib import Path

from whimse.config import Config
from whimse.types.local_modifications import LocalModifications
from whimse.types.policy import Policy

_logger = getLogger(__name__)


class ExploreStageError(Exception):
    pass


class PolicyExplorer[PolicyT: Policy]:
    def __init__(self, config: Config) -> None:
        self._config = config

    @property
    def policy_store(self) -> Path:
        raise NotImplementedError()

    def _read_local_mod_file[
        ContainerT, T
    ](
        self,
        path: Path,
        container: Callable[[Iterable[T]], ContainerT],
        parser: Callable[[str], T],
    ) -> ContainerT:
        try:
            with open(path, "r", encoding="locale") as file:
                return container(
                    parser(line)
                    for line in (line.strip() for line in file)
                    if line and not line.startswith("#")
                )
        except FileNotFoundError:
            return container(())

    def get_local_modifications(self) -> LocalModifications:
        _logger.debug("Reading local policy modifications from %r", self.policy_store)
        return LocalModifications(
            *(
                self._read_local_mod_file(
                    self.policy_store / data_field.metadata["file"],
                    data_field.metadata.get("container", frozenset),
                    data_field.metadata.get("parser", str),
                )
                for data_field in fields(LocalModifications)
            )
        )

    def get_disable_dontaudit_state(self) -> bool:
        _logger.debug("Checking disable dontaudit state in %r", self.policy_store)
        return (self.policy_store / "disable_dontaudit").is_file()

    def get_policy(self) -> "PolicyT":
        raise NotImplementedError()
