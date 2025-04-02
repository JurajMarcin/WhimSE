from logging import getLogger

from whimse.config import Config
from whimse.explore.active import ActivePolicyExplorer
from whimse.explore.distribution import DistPolicyExplorer
from whimse.types.policy import ActivePolicy, DistPolicy

_logger = getLogger(__name__)


def explore_policy(config: Config) -> tuple[ActivePolicy, DistPolicy]:
    _logger.info("Exploring the current policy")
    active_policy = ActivePolicyExplorer(config).get_policy()
    dist_policy = DistPolicyExplorer(config).get_policy()
    return active_policy, dist_policy
