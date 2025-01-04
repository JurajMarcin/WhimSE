import string
from dataclasses import dataclass

TOKEN_CHARS: set[str] = {
    *string.digits,
    *string.ascii_lowercase,
    *string.ascii_uppercase,
    *"[].@=/*-_$%+-!|&^:~`#{}'<>?,",
}


@dataclass(frozen=True)
class CilTreeNode:
    pass


@dataclass(frozen=True)
class CilTreeInnerNode(CilTreeNode):
    children: tuple[CilTreeNode, ...]


@dataclass(frozen=True)
class CilTreeLeaf(CilTreeNode):
    value: str


class CilParserError(Exception):
    pass


class CilParser:
    def __init__(self, cil_text: str, file_name: str) -> None:
        self._cil_text = cil_text
        self._cil_lines = cil_text.splitlines(keepends=True)
        self._file_name = file_name
        self._line = 0
        self._col = 0

    def __iter__(self) -> "CilParser":
        return CilParser(self._cil_text, self._file_name)

    def _context(self) -> str:
        return f"{self._file_name}:{self._line + 1}:{self._col + 1}"

    def _peek(self) -> str:
        if self._line >= len(self._cil_lines):
            raise EOFError
        return self._cil_lines[self._line][self._col]

    def _pop(self) -> str:
        char = self._peek()
        self._col += 1
        while self._line < len(self._cil_lines) and self._col >= len(
            self._cil_lines[self._line]
        ):
            self._col = 0
            self._line += 1
        return char

    def _skip_whitespace(self) -> None:
        while self._peek().isspace():
            self._pop()

    def _next_token(self) -> tuple[str, bool]:
        self._skip_whitespace()

        char = self._peek()
        quoted = False
        if char == '"':
            quoted = True
            self._pop()
        elif char not in TOKEN_CHARS:
            return self._pop(), True

        symbol = ""
        try:
            while True:
                char = self._peek()
                if quoted and char == '"':
                    self._pop()
                    break
                if not quoted and char not in TOKEN_CHARS:
                    break
                symbol += self._pop()
        except EOFError:
            if quoted:
                raise CilParserError(
                    f"Invalid syntax: quoted string ended with EOF at {self._context()}"
                ) from None

        return symbol, False

    def _next_node(self) -> "CilTreeNode | None":
        while (token := self._next_token()) == (";", True):
            while self._pop() != "\n":
                pass
        match token:
            case ("(", True):
                children = []
                try:
                    while (child := self._next_node()) is not None:
                        children.append(child)
                except EOFError:
                    raise CilParserError(
                        f"Invalid syntax: expected ')', but got EOF at {self._context()}"
                    ) from None
                return CilTreeInnerNode(tuple(children))
            case (")", True):
                return None
            case (value, False):
                return CilTreeLeaf(value)
            case (value, _):
                raise CilParserError(
                    f"Invalid syntax: unexpected token '{value}' at {self._context()}"
                )

    def __next__(self) -> "CilTreeNode":
        try:
            node = self._next_node()
            if node is None:
                raise StopIteration
            return node
        except EOFError:
            raise StopIteration from None
        except CilParserError:
            raise
        except Exception as ex:
            raise CilParserError(f"Internal parser error at {self._context()}") from ex

    def parse_cil_root(self) -> CilTreeInnerNode:
        return CilTreeInnerNode(tuple(iter(self)))
