from dataclasses import dataclass

from whimse.config import Config
from whimse.explore.actual import ActualPolicyExplorer
from whimse.explore.actual.types import ActualPolicy
from whimse.explore.distributed import DistPolicyExplorer
from whimse.explore.distributed.types import DistPolicy
from whimse.utils.logging import get_logger

_logger = get_logger(__name__)


@dataclass()
class ExploreStageResult:
    dist_policy: DistPolicy
    actual_policy: ActualPolicy


def explore_stage(config: Config) -> ExploreStageResult:
    _logger.info("Gathering facts about current policy")
    dist_policy = DistPolicyExplorer(config).get_dist_policy()
    actual_policy = ActualPolicyExplorer(config).get_actual_policy()
    return ExploreStageResult(dist_policy, actual_policy)
