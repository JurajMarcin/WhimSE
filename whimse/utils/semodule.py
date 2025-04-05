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

import re
from argparse import ArgumentParser
from collections.abc import Iterable

from whimse.utils.shell import get_command_executions

_SEMODULE_ARG_PARSER = ArgumentParser()
# Default libsemodule priority is 400
_SEMODULE_ARG_PARSER.add_argument(
    "--priority", "-X", action="store", type=int, default=400
)
_SEMODULE_ARG_PARSER.add_argument(
    "--install", "-i", action="extend", nargs="*", default=[]
)


def list_semodule_installs(script: str) -> Iterable[tuple[str, int]]:
    for cmd in get_command_executions(script, re.compile(r"(?:/usr/sbin/)?semodule")):
        args, _ = _SEMODULE_ARG_PARSER.parse_known_args(cmd[1:])
        for file in args.install:
            # TODO: Possibly handle spaces better in parsing
            yield file.strip(), args.priority
