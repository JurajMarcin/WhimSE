from collections.abc import Callable
from dataclasses import Field, dataclass, field, fields
from pathlib import Path

from whimse.config import Config
from whimse.selinux import Boolean, FileContext, SelinuxUser, User, UserLabelingPrefix
from whimse.utils.logging import get_logger

_logger = get_logger(__name__)


@dataclass(frozen=True)
class LocalPolicyModifications:
    booleans: frozenset[Boolean] = field(
        metadata={"file": "active/booleans.local", "const": Boolean.parse}
    )
    file_contexts: frozenset[FileContext] = field(
        metadata={"file": "active/file_context.local", "const": FileContext.parse}
    )
    interfaces: frozenset[str] = field(metadata={"file": "active/interfaces.local"})
    nodes: frozenset[str] = field(metadata={"file": "active/nodes.local"})
    ports: frozenset[str] = field(metadata={"file": "active/ports.local"})
    selinux_users: frozenset[SelinuxUser] = field(
        metadata={"file": "active/users.local", "const": SelinuxUser.parse}
    )
    users: frozenset[User] = field(
        metadata={"file": "active/seusers.local", "const": User.parse}
    )
    user_prefixes: frozenset[UserLabelingPrefix] = field(
        metadata={"file": "active/users_extra.local", "const": UserLabelingPrefix.parse}
    )

    @staticmethod
    def _read_frozenset_field[
        T
    ](policy_store: Path, field: Field[frozenset[T]]) -> frozenset[T]:
        const: Callable[[str], T] = field.metadata.get("const", str)
        try:
            with open(
                policy_store / field.metadata["file"], "r", encoding="locale"
            ) as file:
                return frozenset(
                    const(line.strip())
                    for line in file
                    if line.strip() and not line.strip().startswith("#")
                )
        except FileNotFoundError:
            return frozenset()

    @staticmethod
    def read(policy_store: Path) -> "LocalPolicyModifications":
        _logger.verbose("Reading local policy modifications")
        return LocalPolicyModifications(
            *(
                LocalPolicyModifications._read_frozenset_field(policy_store, field)
                for field in fields(LocalPolicyModifications)
            )
        )


class PolicyExplorer:
    def __init__(self, config: Config) -> None:
        self._config = config
