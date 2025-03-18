from collections.abc import Iterable
from os import listdir

from whimse.explore.actual.types import ActualPolicy
from whimse.explore.common import LocalPolicyModifications, PolicyExplorer
from whimse.selinux import PolicyModule, PolicyModuleLang
from whimse.utils.logging import get_logger

_logger = get_logger(__name__)


class ActualPolicyExplorer(PolicyExplorer):
    def _get_policy_modules(self) -> Iterable[PolicyModule]:
        modules_path = self._explore_config.policy_store_path / "active" / "modules"
        disabled_path = modules_path / "disabled"
        for priority in listdir(modules_path):
            if not priority.isdigit():
                continue
            priority_path = modules_path / priority
            priority_number = int(priority)
            for module_name in listdir(priority_path):
                module_path = priority_path / module_name
                if not (module_path / "lang_ext").is_file():
                    continue
                _logger.verbose(
                    "Found actual module %r with priority %r",
                    module_name,
                    priority_number,
                )
                yield PolicyModule(
                    module_name,
                    priority_number,
                    (disabled_path / module_name).is_file(),
                    frozenset(
                        (lang, str(file))
                        for lang, file in (
                            (PolicyModuleLang.CIL, module_path / "cil"),
                            (PolicyModuleLang.HLL, module_path / "hll"),
                        )
                        if file.is_file()
                    ),
                )

    def get_actual_policy(self) -> ActualPolicy:
        _logger.info("Gathering facts about actual system policy")
        return ActualPolicy(
            frozenset(self._get_policy_modules()),
            LocalPolicyModifications.read(self._explore_config.policy_store_path),
            (self._explore_config.policy_store_path / "disable_dontaudit").is_file(),
        )
