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
from collections.abc import Iterable
from enum import StrEnum
from itertools import chain
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Discriminator, Field


def _list_join(items: Iterable[Any]) -> str:
    return shlex.join(map(str, items))


_CIL_BOOL_STR = {
    False: "false",
    True: "true",
}


class CilBase:
    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        del indent
        raise NotImplementedError()

    def cil_str(self, indent: int = 0) -> str:
        return "\n".join("    " * indent + line for line, indent in self.cil(indent))


def _str_or_cil(value: str | CilBase, indent: int) -> Iterable[tuple[str, int]]:
    if isinstance(value, str):
        yield value, indent
    else:
        yield from value.cil(indent)


class CilNodeBase(CilBase):
    line: int


class CilContainerBase:
    children: list["CilNode"]


class CilExprOperator(StrEnum):
    AND = "and"
    OR = "or"
    NOT = "not"
    ALL = "all"
    EQ = "eq"
    NEQ = "neq"
    XOR = "xor"
    RANGE = "range"
    DOM = "dom"
    DOMBY = "domby"
    INCOMP = "incomp"


class CilExpr(BaseModel, CilBase):
    operator: CilExprOperator | None
    operands: list["str | CilExpr"]

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        if self.operator is None and all(
            isinstance(oper, str) for oper in self.operands
        ):
            yield f"({_list_join(self.operands)})", indent
            return
        if self.operator is None:
            yield "(", indent
        else:
            yield f"({self.operator}", indent
        for oper in self.operands:
            yield from _str_or_cil(oper, indent + 1)
        yield ")", indent


class CilOrdered(BaseModel, CilNodeBase):
    flavor: Literal["classorder", "sensitivityorder", "categoryorder", "sidorder"]
    unordered: bool
    order: list[str]

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        unordered_str = "unordered " if self.unordered else ""
        yield f"({self.flavor} ({unordered_str}{_list_join(self.order)}))", indent


class CilBounds(BaseModel, CilNodeBase):
    flavor: Literal["rolebounds", "typebounds", "userbounds"]
    parent: str
    child: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.parent} {self.child})", indent


#
#  Access Vector Rules
#


class CilAvrule(BaseModel, CilNodeBase):
    flavor: Literal[
        "allow",
        "auditallow",
        "dontaudit",
        "neverallow",
        "deny",
        "allowx",
        "auditallowx",
        "dontauditx",
        "neverallowx",
    ]
    source: str
    target: str
    classperms: "str | CilClassperms | CilPermissionx"

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.source} {self.target}", indent
        yield from _str_or_cil(self.classperms, indent + 1)
        yield ")", indent


#
#  Call # Macro Statements
#


class CilCall(BaseModel, CilNodeBase):
    flavor: Literal["call"]
    macro: str
    args: list[str | list]

    @staticmethod
    def _cil_args(args: list[str | list], indent: int) -> Iterable[tuple[str, int]]:
        yield "(", indent
        for arg in args:
            if isinstance(arg, str):
                yield arg, indent + 1
            else:
                yield from CilCall._cil_args(arg, indent + 1)
        yield ")", indent

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.macro}", indent
        yield from self._cil_args(self.args, indent + 1)
        yield ")", indent


class CilMacroParam(BaseModel):
    type: str
    name: str


class CilMacro(BaseModel, CilNodeBase, CilContainerBase):
    flavor: Literal["macro"]
    id: str
    params: list[CilMacroParam]

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        params_str = (
            "("
            + " ".join(f"({param.type} {param.name})" for param in self.params)
            + ")"
        )
        yield f"({self.flavor} {self.id} {params_str}", indent
        yield from chain(*(child.cil(indent + 1) for child in self.children))
        yield ")", indent


#
#  Class and Permission Statements
#


class CilClassperms(BaseModel, CilNodeBase):
    flavor: Literal["classperms"]
    cls: str = Field(alias="class")
    perms: CilExpr

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.cls}", indent
        yield from self.perms.cil(indent + 1)
        yield ")", indent


class CilClasscommon(BaseModel, CilNodeBase):
    flavor: Literal["classcommon"]
    cls: str = Field(alias="class")
    common: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.cls} {self.common})", indent


class CilClass(BaseModel, CilNodeBase):
    flavor: Literal["class", "common"]
    id: str
    perms: list[str]

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id} ({_list_join(self.perms)}))", indent


class CilClasspermission(BaseModel, CilNodeBase):
    flavor: Literal["classpermission"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilClasspermissionset(BaseModel, CilNodeBase):
    flavor: Literal["classpermissionset"]
    id: str
    classperms: CilClassperms

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id}", indent
        yield from self.classperms.cil(indent + 1)
        yield ")", indent


class CilClassmap(BaseModel, CilNodeBase):
    flavor: Literal["classmap"]
    id: str
    classmappings: list[str]

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id} ({_list_join(self.classmappings)}))", indent


class CilClassmapping(BaseModel, CilNodeBase):
    flavor: Literal["classmapping"]
    classmap: str
    classmapping: str
    classperms: str | CilClassperms

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.classmap} {self.classmapping}", indent
        yield from _str_or_cil(self.classperms, indent + 1)
        yield ")", indent


class CilPermissionxKind(StrEnum):
    IOCTL = "ioctl"
    NLMSG = "nlmsg"


class CilPermissionx(BaseModel, CilNodeBase):
    flavor: Literal["permissionx"]
    id: str | None
    kind: CilPermissionxKind
    cls: str = Field(alias="class")
    perms: CilExpr

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        if self.id is not None:
            yield f"({self.flavor} {self.id}", indent
            indent += 1
        yield f"({self.kind} {self.cls}", indent
        yield from self.perms.cil(indent + 1)
        yield ")", indent
        if self.id is not None:
            indent -= 1
            yield ")", indent


#
#  Conditional Statements
#


class CilBoolean(BaseModel, CilNodeBase):
    flavor: Literal["boolean"]
    id: str
    value: bool

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id} {_CIL_BOOL_STR[self.value]})", indent


class CilCondblock(BaseModel, CilBase, CilContainerBase):
    value: bool

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({_CIL_BOOL_STR[self.value]}", indent
        yield from chain(*(child.cil(indent + 1) for child in self.children))
        yield ")", indent


class CilBooleanif(BaseModel, CilNodeBase):
    flavor: Literal["booleanif"]
    condition: CilExpr
    branches: list[CilCondblock]

    @property
    def children(self) -> Iterable["CilNode"]:
        yield from chain(*(branch.children for branch in self.branches))

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor}", indent
        yield from self.condition.cil(indent + 1)
        yield from chain(*(branch.cil(indent + 1) for branch in self.branches))
        yield ")", indent


class CilTunable(BaseModel, CilNodeBase):
    flavor: Literal["tunable"]
    id: str
    value: bool

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id} {_CIL_BOOL_STR[self.value]})", indent


class CilTunableif(BaseModel, CilNodeBase):
    flavor: Literal["tunableif"]
    condition: CilExpr
    branches: list[CilCondblock]

    @property
    def children(self) -> Iterable["CilNode"]:
        yield from chain(*(branch.children for branch in self.branches))

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor}", indent
        yield from self.condition.cil(indent + 1)
        yield from chain(*(branch.cil(indent + 1) for branch in self.branches))
        yield ")", indent


#
#  Constaint Statements
#


class CilConstrain(BaseModel, CilNodeBase):
    flavor: Literal["constrain", "mlsconstrain"]
    classperms: str | CilClassperms
    constraint: CilExpr

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor}", indent
        yield from _str_or_cil(self.classperms, indent + 1)
        yield from self.constraint.cil(indent + 1)
        yield ")", indent


class CilValidatetrans(BaseModel, CilNodeBase):
    flavor: Literal["validatetrans", "mlsvalidatetrans"]
    cls: str = Field(alias="class")
    constraint: CilExpr

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.cls}", indent
        yield from self.constraint.cil(indent + 1)
        yield ")", indent


#
#  Container Statements
#


class CilBlock(BaseModel, CilNodeBase, CilContainerBase):
    flavor: Literal["block"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id}", indent
        yield from chain(*(child.cil(indent + 1) for child in self.children))
        yield ")", indent


class CilBlockabstract(BaseModel, CilNodeBase):
    flavor: Literal["blockabstract"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilBlockinherit(BaseModel, CilNodeBase):
    flavor: Literal["blockinherit"]
    template: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.template})", indent


class CilOptional(BaseModel, CilNodeBase, CilContainerBase):
    flavor: Literal["optional"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id}", indent
        yield from chain(*(child.cil(indent + 1) for child in self.children))
        yield ")", indent


class CilInPosition(StrEnum):
    AFTER = "after"
    BEFORE = "before"


class CilIn(BaseModel, CilNodeBase, CilContainerBase):
    flavor: Literal["in"]
    position: CilInPosition
    container: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.position} {self.container}", indent
        yield from chain(*(child.cil(indent + 1) for child in self.children))
        yield ")", indent


#
#  Context Statement
#


class CilContext(BaseModel, CilNodeBase):
    flavor: Literal["context"]
    id: str | None
    user: str
    role: str
    type: str
    levelrange: "str | CilLevelrange"

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        if self.id is not None:
            yield f"({self.flavor} {self.id}", indent
            indent += 1
        yield f"({self.user} {self.role} {self.type} ", indent
        yield from _str_or_cil(self.levelrange, indent + 1)
        yield ")", indent
        if self.id is not None:
            indent -= 1
            yield ")", indent


#
#  Default Object Statements
#


class CilDefaultObject(StrEnum):
    SOURCE = "source"
    TARGET = "target"


class CilDefault(BaseModel, CilNodeBase):
    flavor: Literal["defaultuser", "defaultrole", "defaulttype"]
    cls: list[str] = Field(alias="class")
    default: CilDefaultObject

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} ({_list_join(self.cls)}) {self.default})", indent


class CilDefaultrangeObject(StrEnum):
    SOURCE = "source"
    TARGET = "target"
    GLBLUB = "glblub"


class CilDefaulrangeRange(StrEnum):
    LOW = "low"
    HIGH = "high"
    LOW_HIGH = "low-high"


class CilDefaultrange(BaseModel, CilNodeBase):
    flavor: Literal["defaultrange"]
    cls: list[str] = Field(alias="class")
    default: CilDefaultrangeObject
    range: CilDefaulrangeRange | None

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield (
            f"({self.flavor} ({_list_join(self.cls)}) {self.default} "
            f"{self.range if self.range is not None else ''})"
        ), indent


#
#  File Labeling Statements
#


class CilFileconType(StrEnum):
    FILE = "file"
    DIR = "dir"
    CHAR = "char"
    BLOCK = "block"
    SOCKET = "socket"
    PIPE = "pipe"
    SYMLINK = "symlink"
    ANY = "any"


class CilFilecon(BaseModel, CilNodeBase):
    flavor: Literal["filecon"]
    path: str
    file_type: CilFileconType = Field(alias="fileType")
    context: str | CilContext | None

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f'({self.flavor} "{self.path}" {self.file_type}', indent
        if self.context is None:
            yield "()", indent
        else:
            yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


class CilFsuseType(StrEnum):
    TASK = "task"
    TRANS = "trans"
    XATTR = "xattr"


class CilFsuse(BaseModel, CilNodeBase):
    flavor: Literal["fsuse"]
    fs_type: CilFsuseType = Field(alias="fsType")
    fs_name: str = Field(alias="fsName")
    context: str | CilContext

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.fs_type} {self.fs_name}", indent
        yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


class CilGenfscon(BaseModel, CilNodeBase):
    flavor: Literal["genfscon"]
    fs_name: str = Field(alias="fsName")
    path: str
    file_type: CilFileconType = Field(alias="fileType")
    context: str | CilContext

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f'({self.flavor} {self.fs_name} "{self.path}" {self.file_type}', indent
        yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


#
#  Infiniband Statements
#


class CilIbpkeycon(BaseModel, CilNodeBase):
    flavor: Literal["ibpkeycon"]
    subnet: str
    pkey_low: int = Field(alias="pkeyLow")
    pkey_high: int = Field(alias="pkeyHigh")
    context: str | CilContext

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.subnet} ({self.pkey_low} {self.pkey_high})", indent
        yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


class CilIbendportcon(BaseModel, CilNodeBase):
    flavor: Literal["ibendportcon"]
    device: str
    port: int
    context: str | CilContext

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.device} {self.port}", indent
        yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


#
#  Multi-Level Security Labeling Statements
#


class CilSensitivity(BaseModel, CilNodeBase):
    flavor: Literal["sensitivity"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilSensitivityalias(BaseModel, CilNodeBase):
    flavor: Literal["sensitivityalias"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilSensitivityaliasactual(BaseModel, CilNodeBase):
    flavor: Literal["sensitivityaliasactual"]
    sensitivityalias: str
    sensitivity: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.sensitivityalias} {self.sensitivity})", indent


class CilCategory(BaseModel, CilNodeBase):
    flavor: Literal["category"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilCategoryalias(BaseModel, CilNodeBase):
    flavor: Literal["categoryalias"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilCategoryaliasactual(BaseModel, CilNodeBase):
    flavor: Literal["categoryaliasactual"]
    categoryalias: str
    category: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.categoryalias} {self.category})", indent


class CilCategoryset(BaseModel, CilNodeBase):
    flavor: Literal["categoryset"]
    id: str
    category: CilExpr

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id}", indent
        yield from self.category.cil(indent + 1)
        yield ")", indent


class CilSensitivitycategory(BaseModel, CilNodeBase):
    flavor: Literal["sensitivitycategory"]
    sensitivity: str
    category: CilExpr

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.sensitivity}", indent
        yield from self.category.cil(indent + 1)
        yield ")", indent


class CilLevel(BaseModel, CilNodeBase):
    flavor: Literal["level"]
    id: str | None
    sensitivity: str
    category: CilExpr | None

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        if self.id is not None:
            yield f"({self.flavor} {self.id}", indent
            indent += 1
        yield f"({self.sensitivity}", indent
        if self.category is not None:
            yield from self.category.cil(indent + 1)
        yield ")", indent
        if self.id is not None:
            indent -= 1
            yield ")", indent


class CilLevelrange(BaseModel, CilNodeBase):
    flavor: Literal["levelrange"]
    id: str | None
    low: str | CilLevel
    high: str | CilLevel

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        if self.id is not None:
            yield f"({self.flavor} {self.id}", indent
            indent += 1
        yield "(", indent
        yield from _str_or_cil(self.low, indent + 1)
        yield from _str_or_cil(self.high, indent + 1)
        yield ")", indent
        if self.id is not None:
            indent -= 1
            yield ")", indent


class CilRangetransition(BaseModel, CilNodeBase):
    flavor: Literal["rangetransition"]
    source: str
    target: str
    cls: str = Field(alias="class")
    range: str | CilLevelrange

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.source} {self.target} {self.cls}", indent
        yield from _str_or_cil(self.range, indent + 1)
        yield ")", indent


#
#  Network Labeling Statements
#


class CilIpaddr(BaseModel, CilNodeBase):
    flavor: Literal["ipaddr"]
    id: str | None
    ip: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        if self.id is None:
            yield f"({self.ip})", indent
        else:
            yield f"({self.flavor} {self.id} {self.ip})", indent


class CilNetifcon(BaseModel, CilNodeBase):
    flavor: Literal["netifcon"]
    if_name: str = Field(alias="ifName")
    if_context: str | CilContext = Field(alias="ifContext")
    packet_context: str | CilContext = Field(alias="packetContext")

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.if_name}", indent
        yield from _str_or_cil(self.if_context, indent + 1)
        yield from _str_or_cil(self.packet_context, indent + 1)
        yield ")", indent


class CilNodecon(BaseModel, CilNodeBase):
    flavor: Literal["nodecon"]
    subnet: str | CilIpaddr
    mask: str | CilIpaddr
    context: str | CilContext

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield (
            f"({self.flavor} "
            f"{self.subnet if isinstance(self.subnet, str) else self.subnet.cil_str()} "
            f"{self.mask if isinstance(self.mask, str) else self.mask.cil_str()}"
        ), indent
        yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


class CilProtocol(StrEnum):
    TCP = "tcp"
    UDP = "udp"
    DCCP = "dccp"
    SCTP = "sctp"


class CilPortcon(BaseModel, CilNodeBase):
    flavor: Literal["portcon"]
    protocol: CilProtocol
    port_low: int = Field(alias="portLow")
    port_high: int = Field(alias="portHigh")
    context: str | CilContext

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.protocol} ({self.port_low} {self.port_high})", indent
        yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


#
#  Policy Configuration Statements
#


class CilMls(BaseModel, CilNodeBase):
    flavor: Literal["mls"]
    value: bool

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {_CIL_BOOL_STR[self.value]})", indent


class CilHandleunknownAction(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    REJECT = "reject"


class CilHandleunknown(BaseModel, CilNodeBase):
    flavor: Literal["handleunknown"]
    action: CilHandleunknownAction

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.action})", indent


class CilPolicycap(BaseModel, CilNodeBase):
    flavor: Literal["policycap"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


#
#  Role Statements
#


class CilRole(BaseModel, CilNodeBase):
    flavor: Literal["role"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilRoletype(BaseModel, CilNodeBase):
    flavor: Literal["roletype"]
    role: str
    type: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.role} {self.type})", indent


class CilRoleattribute(BaseModel, CilNodeBase):
    flavor: Literal["roleattribute"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilRoleattributeset(BaseModel, CilNodeBase):
    flavor: Literal["roleattributeset"]
    roleattribute: str
    roles: CilExpr

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.roleattribute}", indent
        yield from self.roles.cil(indent + 1)
        yield ")", indent


class CilRoleallow(BaseModel, CilNodeBase):
    flavor: Literal["roleallow"]
    source: str
    target: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.source} {self.target})", indent


class CilRoletransition(BaseModel, CilNodeBase):
    flavor: Literal["roletransition"]
    source: str
    target: str
    cls: str = Field(alias="class")
    result: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.source} {self.target} {self.cls} {self.result})", indent


#
#  SID Statements
#


class CilSid(BaseModel, CilNodeBase):
    flavor: Literal["sid"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilSidcontext(BaseModel, CilNodeBase):
    flavor: Literal["sidcontext"]
    sid: str
    context: str | CilContext

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.sid}", indent
        yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


#
#  Type Statements
#


class CilType(BaseModel, CilNodeBase):
    flavor: Literal["type"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilTypealias(BaseModel, CilNodeBase):
    flavor: Literal["typealias"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilTypealiasactual(BaseModel, CilNodeBase):
    flavor: Literal["typealiasactual"]
    typealias: str
    type: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.typealias} {self.type})", indent


class CilTypeattribute(BaseModel, CilNodeBase):
    flavor: Literal["typeattribute"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilTypeattributeset(BaseModel, CilNodeBase):
    flavor: Literal["typeattributeset"]
    typeattribute: str
    types: CilExpr

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.typeattribute}", indent
        yield from self.types.cil(indent + 1)
        yield ")", indent


class CilExpandtypeattribute(BaseModel, CilNodeBase):
    flavor: Literal["expandtypeattribute"]
    types: list[str]
    expand: bool

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} ({_list_join(self.types)}) {_CIL_BOOL_STR[self.expand]})", indent


class CilTyperule(BaseModel, CilNodeBase):
    flavor: Literal["typechange", "typemember", "typetransition"]
    source: str
    target: str
    cls: str = Field(alias="class")
    name: str | None = None
    result: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        name_str = f' "{self.name}"' if self.name is not None else ""
        yield (
            f"({self.flavor} {self.source} {self.target} "
            f"{self.cls}{name_str} {self.result})",
            indent,
        )


class CilTypepermissive(BaseModel, CilNodeBase):
    flavor: Literal["typepermissive"]
    type: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.type})", indent


#
#  User Statements
#


class CilUser(BaseModel, CilNodeBase):
    flavor: Literal["user"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilUserrole(BaseModel, CilNodeBase):
    flavor: Literal["userrole"]
    user: str
    role: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.user} {self.role})", indent


class CilUserattribute(BaseModel, CilNodeBase):
    flavor: Literal["userattribute"]
    id: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.id})", indent


class CilUserattributeset(BaseModel, CilNodeBase):
    flavor: Literal["userattributeset"]
    userattribute: str
    users: CilExpr

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.userattribute}", indent
        yield from self.users.cil(indent + 1)
        yield ")", indent


class CilUserlevel(BaseModel, CilNodeBase):
    flavor: Literal["userlevel"]
    user: str
    level: str | CilLevel

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.user}", indent
        yield from _str_or_cil(self.level, indent + 1)
        yield ")", indent


class CilUserrange(BaseModel, CilNodeBase):
    flavor: Literal["userrange"]
    user: str
    range: str | CilLevelrange

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.user}", indent
        yield from _str_or_cil(self.range, indent + 1)
        yield ")", indent


class CilUserprefix(BaseModel, CilNodeBase):
    flavor: Literal["userprefix"]
    user: str
    prefix: str

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f'({self.flavor} {self.user} "{self.prefix}")', indent


class CilSelinuxuser(BaseModel, CilNodeBase):
    flavor: Literal["selinuxuser"]
    name: str
    user: str
    range: str | CilLevelrange

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f'({self.flavor} "{self.name}" {self.user}', indent
        yield from _str_or_cil(self.range, indent + 1)
        yield ")", indent


class CilSelinuxuserdefault(BaseModel, CilNodeBase):
    flavor: Literal["selinuxuserdefault"]
    user: str
    range: str | CilLevelrange

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.user}", indent
        yield from _str_or_cil(self.range, indent + 1)
        yield ")", indent


#
#  Xen Statements
#


class CilIomemcon(BaseModel, CilNodeBase):
    flavor: Literal["iomemcon"]
    mem_addr_low: int = Field(alias="memAddrLow")
    mem_addr_high: int = Field(alias="memAddrHigh")
    context: str | CilContext

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} ({self.mem_addr_low} {self.mem_addr_high})", indent
        yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


class CilIoportcon(BaseModel, CilNodeBase):
    flavor: Literal["ioportcon"]
    port_low: int = Field(alias="portLow")
    port_high: int = Field(alias="portHigh")
    context: str | CilContext

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} ({self.port_low} {self.port_high})", indent
        yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


class CilPcidevicecon(BaseModel, CilNodeBase):
    flavor: Literal["pcidevicecon"]
    device: int
    context: str | CilContext

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.device}", indent
        yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


class CilPirqcon(BaseModel, CilNodeBase):
    flavor: Literal["pirqcon"]
    irq: int
    context: str | CilContext

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f"({self.flavor} {self.irq}", indent
        yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


class CilDevicetreecon(BaseModel, CilNodeBase):
    flavor: Literal["devicetreecon"]
    path: str
    context: str | CilContext

    def cil(self, indent: int = 0) -> Iterable[tuple[str, int]]:
        yield f'({self.flavor} "{self.path}"', indent
        yield from _str_or_cil(self.context, indent + 1)
        yield ")", indent


#
#  Diff Structure
#

CilNode = Annotated[
    CilOrdered
    | CilBounds
    | CilAvrule
    | CilCall
    | CilMacro
    | CilClassperms
    | CilClasscommon
    | CilClass
    | CilClasspermission
    | CilClasspermissionset
    | CilClassmap
    | CilClassmapping
    | CilPermissionx
    | CilBoolean
    | CilBooleanif
    | CilTunable
    | CilTunableif
    | CilConstrain
    | CilValidatetrans
    | CilBlock
    | CilBlockabstract
    | CilBlockinherit
    | CilOptional
    | CilIn
    | CilContext
    | CilDefault
    | CilDefaultrange
    | CilFilecon
    | CilFsuse
    | CilGenfscon
    | CilIbpkeycon
    | CilIbendportcon
    | CilSensitivity
    | CilSensitivityalias
    | CilSensitivityaliasactual
    | CilCategory
    | CilCategoryalias
    | CilCategoryaliasactual
    | CilCategoryset
    | CilSensitivitycategory
    | CilLevel
    | CilLevelrange
    | CilRangetransition
    | CilIpaddr
    | CilNetifcon
    | CilNodecon
    | CilPortcon
    | CilMls
    | CilHandleunknown
    | CilPolicycap
    | CilRole
    | CilRoletype
    | CilRoleattribute
    | CilRoleattributeset
    | CilRoleallow
    | CilRoletransition
    | CilSid
    | CilSidcontext
    | CilType
    | CilTypealias
    | CilTypealiasactual
    | CilTypeattribute
    | CilTypeattributeset
    | CilExpandtypeattribute
    | CilTyperule
    | CilTypepermissive
    | CilUser
    | CilUserrole
    | CilUserattribute
    | CilUserattributeset
    | CilUserlevel
    | CilUserrange
    | CilUserprefix
    | CilSelinuxuser
    | CilSelinuxuserdefault
    | CilIomemcon
    | CilIoportcon
    | CilPcidevicecon
    | CilPirqcon
    | CilDevicetreecon,
    Discriminator("flavor"),
]


class CilDiffSide(StrEnum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class CilDiff(BaseModel):
    side: CilDiffSide
    hash: str
    description: str | None
    node: CilNode


class CilDiffContext(BaseModel):
    flavor: str
    line: int
    hash: str


class CilDiffNode(BaseModel):
    left: CilDiffContext
    right: CilDiffContext
    diffs: list[CilDiff]
    children: list["CilDiffNode"]

    @property
    def contains_changes(self) -> bool:
        return len(self.diffs) > 0 or len(self.children) > 0
