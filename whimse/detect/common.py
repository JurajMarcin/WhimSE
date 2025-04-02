from whimse.config import Config
from whimse.types.policy import ActivePolicy, DistPolicy


class ChangesDetector:
    def __init__(
        self, config: Config, active_policy: ActivePolicy, dist_policy: DistPolicy
    ) -> None:
        self._config = config
        self._active_policy = active_policy
        self._dist_policy = dist_policy
