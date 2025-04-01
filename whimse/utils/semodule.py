import re
from argparse import ArgumentParser
from collections.abc import Iterable

from whimse.utils.shell import get_command_executions

_SEMODULE_ARG_PARSER = ArgumentParser()
# Default libsemodule priority is 400
_SEMODULE_ARG_PARSER.add_argument(
    "--priority", "-X", action="store", type=int, default=400
)
_SEMODULE_ARG_PARSER.add_argument(
    "--install", "-i", action="extend", nargs="*", default=[]
)


def list_semodule_installs(script: str) -> Iterable[tuple[str, int]]:
    for cmd in get_command_executions(script, re.compile(r"(?:/usr/sbin/)?semodule")):
        args, _ = _SEMODULE_ARG_PARSER.parse_known_args(cmd[1:])
        for file in args.install:
            # TODO: Possibly handle spaces better in parsing
            yield file.strip(), args.priority
