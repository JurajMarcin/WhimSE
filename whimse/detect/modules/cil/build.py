from collections.abc import Iterable
from dataclasses import KW_ONLY, Field, asdict, dataclass, field, fields, make_dataclass
from hashlib import sha1
from types import UnionType
from typing import get_args, get_origin

from whimse.detect.modules.cil.parse import CilTreeInnerNode, CilTreeLeaf, CilTreeNode
from whimse.utils.logging import get_logger
from whimse.utils.tracing import trace

_logger = get_logger(__name__)


class CilBuildError(Exception):
    pass


@dataclass(frozen=True)
class _CilField:
    cil_type: type["CilNode | frozenset | tuple | str"] = str
    # item_cil_type: type["CilNode | str"] | None = None
    _: KW_ONLY
    allow_name: bool = False
    item_allow_name: bool = False
    id: bool = False
    var: bool = False
    cil_field: bool = field(default=True)

    def f(self, *args, **kwargs):
        return field(  # pylint: disable=invalid-field-call
            *args,
            **kwargs,
            metadata={
                **kwargs.get("metadata", {}),
                **asdict(self),
            },
        )

    @staticmethod
    def from_field(node_field: Field) -> "_CilField | None":
        metadata = node_field.metadata
        if not metadata.get("cil_field", False):
            return None
        return _CilField(
            **{
                key: value
                for key, value in metadata.items()
                if key in _CIL_FIELD_FIELDS
            }
        )


_CIL_FIELD_FIELDS = set(f.name for f in fields(_CilField))


@dataclass(frozen=True)
class _CilTreeVarNode(CilTreeNode):
    children: Iterable[CilTreeNode]


@dataclass(frozen=True, kw_only=True)
class CilNode:
    full_hash: bytes = field(repr=False)
    id_hash: bytes = field(repr=False)

    def __hash__(self) -> int:
        return int.from_bytes(self.full_hash[8:])

    @classmethod
    def _id_hash_start(cls) -> bytes:
        return b""

    @classmethod
    def _id_hash_extra(
        cls, items: list["CilNode | frozenset | tuple | str"]
    ) -> Iterable[bytes]:
        del items
        return ()

    @classmethod
    def const(cls, items: Iterable[CilTreeNode]) -> "CilNode":
        return _build_cil_node(cls, items)


@dataclass(frozen=True, kw_only=True)
class CilStatement(CilNode):
    @classmethod
    def _statement_type(cls) -> str:
        return cls.__name__[3:].lower()

    @classmethod
    def _id_hash_start(cls) -> bytes:
        return cls._statement_type().encode()

    @classmethod
    def const(cls, items: Iterable[CilTreeNode]) -> "CilNode":
        items = iter(items)
        statement_type = next(items)
        if not isinstance(statement_type, CilTreeLeaf):
            raise CilBuildError(
                f"Expected CIL statement type name but got {statement_type}"
            )
        if statement_type.value not in CIL_STATEMENTS:
            raise CilBuildError(f"Unknown statement type {statement_type.value}")
        statement_cls = CIL_STATEMENTS[statement_type.value]
        return _build_cil_node(statement_cls, items)


@dataclass(frozen=True)
class CilRoot(CilNode):
    statements: frozenset[CilStatement] = _CilField(
        frozenset[CilStatement], var=True
    ).f()


###################################
# CLASS AND PERMISSION STATEMENTS #
###################################


@dataclass(frozen=True)
class CilCommon(CilStatement):
    common_id: str = _CilField(id=True).f()
    permissions: frozenset[str] = _CilField(frozenset[str]).f()


@dataclass(frozen=True)
class CilClasscommon(CilStatement):
    class_id: str = _CilField(id=True).f()
    common_id: str = _CilField(id=True).f()


@dataclass(frozen=True)
class CilClass(CilStatement):
    class_id: str = _CilField(id=True).f()
    permissions: frozenset[str] = _CilField(frozenset[str]).f()


@dataclass(frozen=True)
class CilClassorder(CilStatement):
    order: tuple[str, ...] = _CilField().f()


@dataclass(frozen=True)
class CilClasspermission(CilStatement):
    classpermissionset_id: str = _CilField(id=True).f()


@dataclass(frozen=True)
class CilClasspermissionsetDecl(CilNode):
    class_id: str = _CilField(id=True).f()
    permissions: frozenset[str] = _CilField().f()  # TODO: expressions


# TODO: classpermissionsset


@dataclass(frozen=True)
class CilClassmap(CilStatement):
    classmap_id: str = _CilField(id=True).f()
    classmapping_ids: frozenset[str] = _CilField().f()


# TODO: classmapping

# TODO: permissionx


#######################
# ACCESS VECTOR RULES #
#######################


@dataclass(frozen=True)
class _CilAvRule(CilStatement):
    source_id: str = _CilField(id=True).f()
    target_id: str = _CilField(id=True).f()
    classpermissionset: CilClasspermissionsetDecl | str = _CilField().f()

    @classmethod
    def _id_hash_extra(
        cls, items: list["CilNode | frozenset | tuple | str"]
    ) -> Iterable[bytes]:
        yield from super()._id_hash_extra(items)
        match items[2]:
            case str() as classpermissionset_id:
                yield classpermissionset_id.encode()
            case CilClasspermissionsetDecl(class_id=class_id):
                yield class_id.encode()


@dataclass(frozen=True)
class CilAllow(_CilAvRule):
    pass


@dataclass(frozen=True)
class CilAuditallow(_CilAvRule):
    pass


@dataclass(frozen=True)
class CilDontaudit(_CilAvRule):
    pass


@dataclass(frozen=True)
class CilNeverallow(_CilAvRule):
    pass


@dataclass(frozen=True)
class CilDeny(_CilAvRule):
    pass


# TODO: allowx, auditallowx, dontauditx, neverallowx

########################
# Container statements #
########################


@dataclass(frozen=True)
class CilBlock(CilStatement):
    block_id: str = _CilField(id=True).f()
    statements: frozenset[CilStatement] = _CilField(var=True).f()


@dataclass(frozen=True)
class CilBlockabstract(CilStatement):
    template_id: str = _CilField(id=True).f()


@dataclass(frozen=True)
class CilBlockinherit(CilStatement):
    template_id: str = _CilField(id=True).f()


@dataclass(frozen=True)
class CilOptional(CilStatement):
    optional_id: str = _CilField().f()
    statements: frozenset[CilStatement] = _CilField(var=True).f()


@dataclass(frozen=True)
class CilIn(CilStatement):
    position: str = _CilField(id=True).f()
    container_id: str = _CilField(id=True).f()
    statements: frozenset[CilStatement] = _CilField(var=True).f()


#######################
# Statements database #
#######################


@trace(_logger)
def _get_statement_types(
    cls: type[CilStatement] = CilStatement,
) -> Iterable[type[CilStatement]]:
    for subcls in cls.__subclasses__():
        if subcls.__name__[0] != "_":
            yield subcls
        yield from _get_statement_types(subcls)


CIL_STATEMENTS = {
    statement_cls._statement_type(): statement_cls
    for statement_cls in _get_statement_types()
}


################
# Constructors #
################


def _build_cil_item(
    node: CilTreeNode,
    cil_type: type["CilNode | frozenset | tuple | str"],
    allow_name: bool,
    item_cil_type: type["CilNode | str"] | None = None,
    item_allow_name: bool = False,
) -> tuple["CilNode | frozenset | tuple | str", bytes]:
    if issubclass(cil_type, CilNode):
        if isinstance(node, CilTreeInnerNode):
            cil_node = cil_type.const(node.children)
            return cil_node, cil_node.full_hash
        if isinstance(node, CilTreeLeaf) and allow_name:
            return node.value, node.value.encode()
        raise CilBuildError(f"Expected CIL statement, but got {node}")
    if issubclass(cil_type, tuple | frozenset):
        if isinstance(node, CilTreeInnerNode | _CilTreeVarNode):
            assert item_cil_type is not None
            cil_items = []
            cil_item_hashes: list[bytes] = []
            for item in node.children:
                cil_item, cil_item_hash = _build_cil_item(
                    item, item_cil_type, item_allow_name
                )
                cil_items.append(cil_item)
                cil_item_hashes.append(cil_item_hash)
            if issubclass(cil_type, frozenset):
                cil_item_hashes.sort()
            return cil_type(cil_items), b"".join(cil_item_hashes)
        raise CilBuildError(f"Expected CIL list or CIL set, but got {node}")
    if issubclass(cil_type, str):
        if isinstance(node, CilTreeLeaf):
            return node.value, node.value.encode()
        raise CilBuildError(f"Expected symbol, but got {node}")
    assert False


def _expand_type_simple(cil_field_type: type) -> tuple[type, bool]:
    base_type = get_origin(cil_field_type)
    if base_type is UnionType:
        type_args = get_args(cil_field_type)
        assert len(type_args) == 2, "There can be at most 2 type args in union"
        assert type_args[1] is str, "Second type arg in union must be str"
        return type_args[0], True
    return cil_field_type, False


def _expand_type(cil_field_type: type) -> tuple[type, bool, type | None, bool]:
    cil_field_type, allow_name = _expand_type_simple(cil_field_type)
    base_type = get_origin(cil_field_type)
    item_type = None
    item_allow_name = False
    if base_type is frozenset or base_type is tuple:
        type_args = get_args(cil_field_type)
        assert len(type_args) > 0
        item_type, item_allow_name = _expand_type_simple(type_args[0])
        cil_field_type = base_type
    return cil_field_type, allow_name, item_type, item_allow_name


def _build_cil_node(
    cil_node_type: type[CilNode], items: Iterable[CilTreeNode]
) -> "CilNode":
    cil_items = []
    hash_builder = sha1(cil_node_type._id_hash_start())
    content_to_hash: list[bytes] = []
    items = iter(items)
    for node_field in fields(cil_node_type):
        if not (cil_field := _CilField.from_field(node_field)):
            continue
        item = next(items) if not cil_field.var else _CilTreeVarNode(children=items)
        cil_item, cil_item_hash = _build_cil_item(
            item,
            *_expand_type(node_field.type),
            # cil_field.cil_type,
            # cil_field.allow_name,
            # cil_field.item_cil_type,
            # cil_field.item_allow_name,
        )
        cil_items.append(cil_item)
        if cil_field.id:
            hash_builder.update(cil_item_hash)
        else:
            content_to_hash.append(cil_item_hash)
    try:
        extra_node = next(items)
        raise CilBuildError(f"Unexpected extra node: {extra_node}")
    except StopIteration:
        pass
    for extra_id in cil_node_type._id_hash_extra(cil_items):
        hash_builder.update(extra_id)
    id_hash = hash_builder.digest()
    for content in content_to_hash:
        hash_builder.update(content)
    full_hash = hash_builder.digest()
    return cil_node_type(*cil_items, full_hash=full_hash, id_hash=id_hash)
