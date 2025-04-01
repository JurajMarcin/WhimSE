from logging import getLogger

from whimse.detect.common import ChangesDetector
from whimse.detect.local_modifications import LocalModificationsChangesDetector
from whimse.detect.modules import PolicyModulesChangeDetector
from whimse.types.reports import (
    DisableDontauditReport,
    LocalModificationsReport,
    PolicyModuleReport,
    Report,
)

_logger = getLogger(__name__)


class PolicyChangesDetector(ChangesDetector):
    def _get_disable_dontaudit_report(self) -> DisableDontauditReport:
        _logger.info("Detecting changes in the disable_dontaudit setting")
        return DisableDontauditReport(
            self._actual_policy.disable_dontaudit,
            self._dist_policy.disable_dontaudit,
        )

    def _get_local_modifications_reports(self) -> list[LocalModificationsReport]:
        return list(
            LocalModificationsChangesDetector(
                self._config, self._actual_policy, self._dist_policy
            ).get_local_modifications_reports()
        )

    def _get_policy_module_reports(self) -> list[PolicyModuleReport]:
        return list(
            PolicyModulesChangeDetector(
                self._config, self._actual_policy, self._dist_policy
            ).get_policy_module_reports()
        )

    def get_report(self) -> Report:
        _logger.info("Detecting changes in the policy")
        return Report(
            disable_dontaudit=self._get_disable_dontaudit_report(),
            local_modifications=self._get_local_modifications_reports(),
            policy_modules=self._get_policy_module_reports(),
        )
