from dataclasses import dataclass

from whimse.explore.common import LocalPolicyModifications
from whimse.selinux import PolicyModule


@dataclass(frozen=True)
class ActualPolicy:
    modules: frozenset[PolicyModule]
    local_modifications: LocalPolicyModifications
    dontaudit_disabled: bool
