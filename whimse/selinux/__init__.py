import shlex
from collections import deque
from dataclasses import dataclass
from enum import StrEnum

from whimse.utils.logging import get_logger

_logger = get_logger(__name__)


@dataclass(frozen=True)
class Statement:
    pass


@dataclass(frozen=True)
class SecurityLevel:
    sensitivity: str
    categories: str | None

    @staticmethod
    def parse(string: str) -> "SecurityLevel":
        data = string.split(":", 2)
        return SecurityLevel(data[0], data[1] if len(data) > 1 else None)

    @staticmethod
    def parse_range(string: str) -> "tuple[SecurityLevel, SecurityLevel]":
        data = list(subs.strip() for subs in string.split("-", 2))
        low = (high := SecurityLevel.parse(data[0]))
        if len(data) > 1:
            high = SecurityLevel.parse(data[1])
        return (low, high)


@dataclass(frozen=True)
class SecurityContext:
    user: str
    role: str
    type: str
    mls_range: tuple[SecurityLevel, SecurityLevel] | None

    @staticmethod
    def parse(string: str) -> "SecurityContext":
        data = string.split(":", 4)
        if len(data) < 3:
            raise ValueError(f"Invalid security context '{string}'")
        return SecurityContext(
            data[0],
            data[1],
            data[2],
            SecurityLevel.parse_range(data[3]) if len(data) > 3 else None,
        )


@dataclass(frozen=True)
class Boolean(Statement):
    name: str
    value: bool

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
    BLOCK_DEVICE = "block_DEVICE"
    CHARACTER_DEVICE = "character_device"
    DIRECTORY = "directory"
    NAMED_PIPE = "named_pipe"
    SYMBOLIC_LINK = "symbolic_link"
    SOCKET_FILE = "socket_file"
    REGULAR_FILE = "regular_file"
    ALL = "all"

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
            case "" | None:
                return FileContextFileType.ALL
        raise ValueError(f"Invalid file context file type '{string}'")


@dataclass(frozen=True)
class FileContext(Statement):
    pathname_regexp: str
    file_type: FileContextFileType
    context: SecurityContext

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
            SecurityContext.parse(data[-1]),
        )


@dataclass(frozen=True)
class User(Statement):
    name: str
    is_group: bool
    selinux_user: str
    mls_range: tuple[SecurityLevel, SecurityLevel] | None

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
            data[0],
            is_group,
            data[1],
            SecurityLevel.parse_range(data[2]) if len(data) == 3 else None,
        )


@dataclass(frozen=True)
class UserLabelingPrefix(Statement):
    selinux_user: str
    prefix: str

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
class SelinuxUser(Statement):
    name: str
    roles: frozenset[str]
    mls_level: SecurityLevel | None
    mls_range: tuple[SecurityLevel, SecurityLevel] | None

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
                mls_range = SecurityLevel.parse_range(dataq.popleft())
            else:
                mls_range = None

            return SelinuxUser(name, frozenset(roles), mls_level, mls_range)
        except (StopIteration, AssertionError):
            raise ValueError(f"Invalid selinux user statement '{string}") from None


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
