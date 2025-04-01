from logging import getLogger

from whimse.config import Config
from whimse.explore.actual import ActualPolicyExplorer
from whimse.explore.distributed import DistPolicyExplorer
from whimse.types.policy import ActualPolicy, DistPolicy

_logger = getLogger(__name__)


def explore_stage(config: Config) -> tuple[ActualPolicy, DistPolicy]:
    _logger.info("Exploring the current policy")
    actual_policy = ActualPolicyExplorer(config).get_policy()
    dist_policy = DistPolicyExplorer(config).get_policy()
    return actual_policy, dist_policy
