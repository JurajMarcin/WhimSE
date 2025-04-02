from collections.abc import Iterable
from logging import getLogger
from os import listdir
from pathlib import Path

from whimse.explore.common import PolicyExplorer
from whimse.types.modules import PolicyModule, PolicyModuleLang
from whimse.types.policy import ActivePolicy

_logger = getLogger(__name__)


class ActivePolicyExplorer(PolicyExplorer[ActivePolicy]):
    @property
    def policy_store(self) -> Path:
        return self._config.policy_store_path

    def _get_policy_modules(self) -> Iterable[PolicyModule]:
        _logger.debug(
            "Gathering modules from the active policy from %r", self.policy_store
        )
        modules_path = self.policy_store / "active" / "modules"
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
                _logger.debug(
                    "Found module %r at priority %r",
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

    def get_policy(self) -> ActivePolicy:
        _logger.info("Gathering facts about the active policy")
        return ActivePolicy(
            self.get_local_modifications(),
            self.get_disable_dontaudit_state(),
            frozenset(self._get_policy_modules()),
        )
