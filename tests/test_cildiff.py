from os import environ
from pathlib import Path
from subprocess import PIPE, run

from whimse.types.cildiff import CilDiffNode

CILDIFF = environ.get(
    "CILDIFF_BINARY", Path(__file__).parent.parent / "cildiff/src/cildiff"
)
TEST_FILE = environ.get("TEST_CIL_FILE", Path(__file__).parent / "all.cil")


def test_cildiff() -> None:
    cildiff_run = run(
        [CILDIFF, "--json", TEST_FILE, "/dev/null"], check=True, stdout=PIPE, text=True
    )

    diff_node = CilDiffNode.model_validate_json(cildiff_run.stdout)

    assert len(diff_node.diffs) == 166  # There are 166 top level statements in all.cil
    assert len(diff_node.children) == 0

    cil = "\n".join(diff.node.cil_str() for diff in diff_node.diffs)

    cildiff_run2 = run(
        [CILDIFF, "--json", TEST_FILE, "-"],
        check=True,
        stdout=PIPE,
        text=True,
        input=cil,
    )

    diff_node2 = CilDiffNode.model_validate_json(cildiff_run2.stdout)

    print("diff_node2.diffs =", len(diff_node2.diffs))
    print("diff_node2.children =", len(diff_node2.children))
    assert len(diff_node2.diffs) == 0
    assert len(diff_node2.children) == 0
