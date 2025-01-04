import subprocess
from functools import wraps

from whimse.utils.logging import Logger


@wraps(subprocess.run)
def run(
    *outer_args,
    logger: Logger,
    check: bool,
    **outer_kwargs,
):
    def _run(*args, stdout=None, stderr=None, **kwargs):
        process = subprocess.run(
            *args,
            stdout=stdout if stdout else subprocess.PIPE,
            stderr=stderr if stderr else subprocess.PIPE,
            check=check,
            **kwargs,
        )
        return process

    return _run(*outer_args, **outer_kwargs)
