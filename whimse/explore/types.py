from dataclasses import dataclass
from pathlib import Path


@dataclass()
class ExploreStageConfig:
    policy_store_path: Path


class ExploreStageError(Exception):
    pass
