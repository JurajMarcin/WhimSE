from whimse.config import Config
from whimse.types.policy import ActualPolicy, DistPolicy


class ChangesDetector:
    def __init__(
        self, config: Config, actual_policy: ActualPolicy, dist_policy: DistPolicy
    ) -> None:
        self._config = config
        self._actual_policy = actual_policy
        self._dist_policy = dist_policy
