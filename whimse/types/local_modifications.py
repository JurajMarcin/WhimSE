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

import shlex
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum


@dataclass(frozen=True)
class LocalModificationStatement:
    pass


@dataclass(frozen=True)
class SecurityLevel:
    sensitivity: str
    categories: str | None

    def __str__(self) -> str:
        return (
            f"{self.sensitivity}:{self.categories}"
            if self.categories
            else f"{self.sensitivity}"
        )

    @staticmethod
    def parse(string: str) -> "SecurityLevel":
        data = string.split(":", 2)
        return SecurityLevel(data[0], data[1] if len(data) > 1 else None)


@dataclass(frozen=True)
class SecurityRange:
    low: SecurityLevel
    high: SecurityLevel | None

    def __str__(self) -> str:
        return f"{self.low}-{self.high}" if self.high else f"{self.low}"

    @staticmethod
    def parse(string: str) -> "SecurityRange":
        data = list(subs.strip() for subs in string.split("-", 2))
        low = SecurityLevel.parse(data[0])
        high = SecurityLevel.parse(data[1]) if len(data) > 1 else None
        return SecurityRange(low, high)


@dataclass(frozen=True)
class SecurityContext:
    user: str
    role: str
    type: str
    mls_range: SecurityRange | None

    def __str__(self) -> str:
        return (
            f"{self.user}:{self.role}:{self.type}:{self.mls_range}"
            if self.mls_range
            else f"{self.user}:{self.role}:{self.type}"
        )

    @staticmethod
    def parse(string: str) -> "SecurityContext":
        data = string.split(":", 4)
        if len(data) < 3:
            raise ValueError(f"Invalid security context '{string}'")
        return SecurityContext(
            data[0],
            data[1],
            data[2],
            SecurityRange.parse(data[3]) if len(data) > 3 else None,
        )


@dataclass(frozen=True)
class Boolean(LocalModificationStatement):
    name: str
    value: bool

    def __str__(self) -> str:
        return f"{self.name}={str(self.value).lower()}"

    @staticmethod
    def parse(string: str) -> "Boolean":
        data = string.split("=")
        if len(data) != 2:
            raise ValueError(f"Invalid boolean modification '{string}': missing =")
        try:
            return Boolean(data[0].strip(), bool(data[1]))
        except ValueError as e:
            raise ValueError(
                f"Invalid boolean modification '{string}': invalid bool value"
            ) from e


class FileContextFileType(StrEnum):
    BLOCK_DEVICE = "-b"
    CHARACTER_DEVICE = "-c"
    DIRECTORY = "-d"
    NAMED_PIPE = "-p"
    SYMBOLIC_LINK = "-l"
    SOCKET_FILE = "-s"
    REGULAR_FILE = "--"
    ALL = ""

    @staticmethod
    def parse(string: str) -> "FileContextFileType":
        match string:
            case "-b":
                return FileContextFileType.BLOCK_DEVICE
            case "-c":
                return FileContextFileType.CHARACTER_DEVICE
            case "-d":
                return FileContextFileType.DIRECTORY
            case "-p":
                return FileContextFileType.NAMED_PIPE
            case "-l":
                return FileContextFileType.SYMBOLIC_LINK
            case "-s":
                return FileContextFileType.SOCKET_FILE
            case "--":
                return FileContextFileType.REGULAR_FILE
            case "":
                return FileContextFileType.ALL
        raise ValueError(f"Invalid file context file type '{string}'")


@dataclass(frozen=True)
class FileContext(LocalModificationStatement):
    pathname_regexp: str
    file_type: FileContextFileType
    context: SecurityContext | None

    def __str__(self) -> str:
        return (
            f"{self.pathname_regexp} {self.file_type} "
            f"{self.context if self.context else '<<none>>'}"
        )

    @staticmethod
    def parse(string: str) -> "FileContext":
        data = shlex.split(string)
        if len(data) != 2 and len(data) != 3:
            raise ValueError(f"Invalid file context '{string}'")
        return FileContext(
            data[0],
            (
                FileContextFileType.parse(data[1])
                if len(data) == 3
                else FileContextFileType.ALL
            ),
            SecurityContext.parse(data[-1]) if data[-1] != "<<none>>" else None,
        )


@dataclass(frozen=True)
class User(LocalModificationStatement):
    is_group: bool
    name: str
    selinux_user: str
    mls_range: SecurityRange | None

    def __str__(self) -> str:
        return f"{'%' if self.is_group else '' }{self.name}:{self.selinux_user}" + (
            f":{self.mls_range}" if self.mls_range else ""
        )

    @staticmethod
    def parse(string: str) -> "User":
        if string.startswith("%"):
            is_group = True
            string = string[1:]
        else:
            is_group = False
        data = string.split(":", 3)
        if len(data) < 2:
            raise ValueError(f"Invalid user statement '{string}'")
        return User(
            is_group,
            data[0],
            data[1],
            SecurityRange.parse(data[2]) if len(data) == 3 else None,
        )


@dataclass(frozen=True)
class UserLabelingPrefix(LocalModificationStatement):
    selinux_user: str
    prefix: str

    def __str__(self) -> str:
        return f"user {self.selinux_user} prefix {self.prefix};"

    @staticmethod
    def parse(string: str) -> "UserLabelingPrefix":
        data = string.split()
        if (
            len(data) != 4
            or data[0] != "user"
            or data[2] != "prefix"
            or data[3][-1] != ";"
        ):
            raise ValueError(f"Invalid user labeling statement '{string}")
        return UserLabelingPrefix(data[1], data[3][:-1])


@dataclass(frozen=True)
class SelinuxUser(LocalModificationStatement):
    user: str
    roles: frozenset[str]
    mls_level: SecurityLevel | None
    mls_range: SecurityRange | None

    def __str__(self) -> str:
        return (
            f"user {self.user} roles {{ {' '.join(self.roles)} }}"
            + (f" level {self.mls_level}" if self.mls_level else "")
            + (f" range {self.mls_range}" if self.mls_range else "")
        )

    @staticmethod
    def parse(string: str) -> "SelinuxUser":
        data = shlex.split(string)
        try:
            assert data[-1][-1] == ";"
            data[-1] = data[-1][:-1].strip()
            dataq = deque(data)

            assert dataq.popleft() == "user"
            name = dataq.popleft()

            if dataq[0] == "roles":
                dataq.popleft()
                role = dataq.popleft()
                if role == "{":
                    roles = set()
                    while (role := dataq.popleft()) != "}":
                        roles.add(role)
                else:
                    roles = {role}
            else:
                roles = set()

            if dataq[0] == "level":
                dataq.popleft()
                mls_level = SecurityLevel.parse(dataq.popleft())
            else:
                mls_level = None

            if dataq[0] == "range":
                dataq.popleft()
                mls_range = SecurityRange.parse(dataq.popleft())
            else:
                mls_range = None

            return SelinuxUser(name, frozenset(roles), mls_level, mls_range)
        except (StopIteration, AssertionError):
            raise ValueError(f"Invalid selinux user statement '{string}") from None


@dataclass(frozen=True)
class LocalModifications:
    booleans: frozenset[Boolean] = field(
        metadata={"file": "active/booleans.local", "parser": Boolean.parse}
    )
    file_contexts: tuple[FileContext, ...] = field(
        metadata={
            "file": "active/file_contexts.local",
            "parser": FileContext.parse,
            "container": tuple,
        }
    )
    interfaces: frozenset[str] = field(metadata={"file": "active/interfaces.local"})
    nodes: frozenset[str] = field(metadata={"file": "active/nodes.local"})
    ports: frozenset[str] = field(metadata={"file": "active/ports.local"})
    selinux_users: frozenset[SelinuxUser] = field(
        metadata={"file": "active/users.local", "parser": SelinuxUser.parse}
    )
    users: frozenset[User] = field(
        metadata={"file": "active/seusers.local", "parser": User.parse}
    )
    user_prefixes: frozenset[UserLabelingPrefix] = field(
        metadata={
            "file": "active/users_extra.local",
            "parser": UserLabelingPrefix.parse,
        }
    )
