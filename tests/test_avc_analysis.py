# pylint: disable=protected-access
from unittest.mock import Mock

from setools.policyrep import InvalidType, SELinuxPolicy, Type, TypeAttribute

from whimse.analyze.avc import AVRuleAVCMatcher
from whimse.types.cildiff import (
    CilDiff,
    CilDiffContext,
    CilDiffNode,
    CilDiffSide,
)
from whimse.types.local_modifications import (
    SecurityContext,
    SecurityLevel,
    SecurityRange,
)
from whimse.utils.avc import AVCEvent

AVC = AVCEvent(
    text="sample text",
    denied=True,
    perms="read",
    scontext=SecurityContext(
        "system_u",
        "system_r",
        "httpd_t",
        SecurityRange(SecurityLevel("s0", None), None),
    ),
    tcontext=SecurityContext(
        "system_u",
        "system_r",
        "httpd_sys_content_t",
        SecurityRange(SecurityLevel("s0", None), None),
    ),
    tcls="file",
    permissive=False,
)

DIFFS = [
    CilDiff.model_validate(
        {
            "side": "LEFT",
            "hash": "diff1",
            "description": None,
            "node": {
                "flavor": "allow",
                "source": "httpd_t",
                "target": "httpd_sys_content_t",
                "classperms": {
                    "flavor": "classperms",
                    "class": "file",
                    "perms": {"operator": None, "operands": ["read", "write"]},
                    "line": 1,
                },
                "line": 1,
            },
        }
    ),
    CilDiff.model_validate(
        {
            "side": "RIGHT",
            "hash": "diff2",
            "description": None,
            "node": {
                "flavor": "allow",
                "source": "httpd_t",
                "target": "httpd_sys_content_t",
                "classperms": {
                    "flavor": "classperms",
                    "class": "file",
                    "perms": {"operator": None, "operands": ["read", "write", "open"]},
                    "line": 1,
                },
                "line": 1,
            },
        }
    ),
    CilDiff.model_validate(
        {
            "side": "RIGHT",
            "hash": "diff3",
            "description": None,
            "node": {
                "flavor": "allow",
                "source": "httpd_t",
                "target": "httpd_content",
                "classperms": {
                    "flavor": "classperms",
                    "class": "file",
                    "perms": {"operator": None, "operands": ["read", "write", "open"]},
                    "line": 2,
                },
                "line": 2,
            },
        }
    ),
]


DIFF_NODE = CilDiffNode(
    left=CilDiffContext(flavor="<root>", line=0, hash="r1"),
    right=CilDiffContext(flavor="<root>", line=0, hash="r2"),
    diffs=DIFFS,
    children=[],
)


def _lookup_type(name: str, deref: bool = True) -> Type:
    del deref
    match name:
        case "httpd_sys_content_t":
            mock_attr = Mock(TypeAttribute)
            mock_attr.name = "httpd_content"
            mock_type = Mock(Type)
            mock_type.attributes.return_value = (mock_attr,)
            mock_type.aliases.return_value = ()
            return mock_type
        case _:
            raise InvalidType()


POLICY = Mock(SELinuxPolicy)
POLICY.lookup_type = Mock(wraps=_lookup_type)


def test_allow_rule_avc_matcher_filtering() -> None:
    actual = list(AVRuleAVCMatcher(AVC, POLICY)._filter_diffs(DIFFS))
    assert len(actual) == 3


def test_allow_rule_avc_matcher_balancing() -> None:
    actual = list(AVRuleAVCMatcher(AVC, POLICY)._balance_diffs(DIFFS))
    assert len(actual) == 1
    assert actual[0].side == CilDiffSide.RIGHT
    assert actual[0].hash == "diff3"


def test_allow_rule_avc_matcher() -> None:
    actual = list(AVRuleAVCMatcher(AVC, POLICY).get_related_diffs(DIFF_NODE))
    assert len(actual) == 1
    actual_node, actual_diff, actual_diff_node = actual[0]
    assert actual_node == DIFFS[2].node
    assert actual_diff == DIFFS[2]
    assert actual_diff_node == DIFF_NODE
