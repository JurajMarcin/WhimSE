from dataclasses import dataclass

from whimse.explore.common import LocalPolicyModifications
from whimse.selinux import PolicyModule


@dataclass()
class ActualPolicy:
    modules: set[PolicyModule]
    local_modifications: LocalPolicyModifications
    dontaudit_disabled: bool
