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
import shlex
from collections.abc import Iterable
from itertools import chain
from pathlib import Path
from re import Pattern


def _expand_single(
    tokens: tuple[str, ...], name: str, values: set[str]
) -> Iterable[tuple[str, ...]]:
    for value in values:
        yield tuple(
            token.replace(f"${{{name}}}", value).replace(f"${name}", value)
            for token in tokens
        )


def _expand_env(
    tokens: tuple[str, ...], env: dict[str, set[str]]
) -> Iterable[tuple[str, ...]]:
    old_partially_expanded: list[tuple[str, ...]] = [tokens]
    for name, values in sorted(env.items(), key=lambda kv: len(kv[0]), reverse=True):
        new_partially_expanded: list[tuple[str, ...]] = []
        for partially_expanded in old_partially_expanded:
            new_partially_expanded.extend(
                _expand_single(partially_expanded, name, values)
            )
        old_partially_expanded = new_partially_expanded
    yield from old_partially_expanded


def _get_commands(tokens: list[str]) -> Iterable[tuple[str, ...]]:
    cmd: list[str] = []
    for token in tokens:
        if token in ("||", "&&", "&", "|", ";", "do"):
            if len(cmd) > 0:
                yield tuple(cmd)
                cmd = []
        elif len(token) > 0 and token[-1] == ";":
            cmd.append(token[:-1])
            yield tuple(cmd)
            cmd = []
        else:
            cmd.append(token)
    if len(cmd) > 0:
        yield tuple(cmd)


def get_command_executions(
    script: str, cmd_pattern: Pattern, env: dict[str, set[str]] | None = None
) -> Iterable[tuple[str, ...]]:
    lines = iter(script.splitlines())
    if env is None:
        env = {}
    while True:
        line = None
        try:
            line = next(lines)
            while len(line) >= 1 and line[-1] == "\\":
                line = line[:-1]
                # Separate to remove '\' even if next() raises StopIteration here
                line += " " + next(lines)
        except StopIteration:
            if line is None:
                return

        while True:
            try:
                tokens = shlex.split(line, comments=True)
                break
            except ValueError as ex:
                if ex.args != ("No closing quotation",):
                    raise
                try:
                    line += next(lines)
                except StopIteration:
                    raise ex from None

        for cmd in _get_commands(tokens):
            if (
                len(cmd) == 2
                and cmd[0] == "export"
                and re.match(r"^(?P<name>[a-zA-Z0-9_]+)\+?=(?P<value>.*)$", cmd[1])
            ):
                cmd = cmd[1:]
            if len(cmd) > 0 and cmd_pattern.match(cmd[0]):
                yield from _expand_env(cmd, env)
            elif (
                len(cmd) == 1
                and (
                    match := re.match(
                        r"^(?P<name>[a-zA-Z0-9_]+)=(?P<value>.*)$", cmd[0]
                    )
                )
                is not None
            ):
                env[match.group("name")] = {
                    t[0] for t in _expand_env((match.group("value"),), env)
                }
            elif (
                len(cmd) == 1
                and (
                    match := re.match(
                        r"^(?P<name>[a-zA-Z0-9_]+)\+=(?P<value>.*)$", cmd[0]
                    )
                )
                is not None
            ):
                expanded = list(_expand_env((match.group("value"),), env))
                env[match.group("name")] = {
                    f"{t1}{t2[0]}"
                    for t1 in env.get(match.group("name"), {""})
                    for t2 in expanded
                }
            elif len(cmd) >= 4 and cmd[0] == "for" and cmd[2] == "in":
                env[cmd[1]] = set(chain(*_expand_env(cmd[3:], env)))
            elif (
                len(cmd) == 2
                and cmd[0] == "."
                and (include_path := Path(cmd[1])).is_file()
            ):
                yield from get_command_executions(
                    include_path.read_text(encoding="locale"), cmd_pattern, env
                )
