import shlex
import subprocess
from functools import wraps
from logging import Logger


@wraps(subprocess.run)
def run(
    *outer_args,
    logger: Logger,
    check: bool,
    **outer_kwargs,
):
    def _run(*args, stdout=None, stderr=None, **kwargs):
        logger.debug(
            "Executing: %r",
            shlex.join(map(str, args[0])) if isinstance(args[0], list) else args[0],
        )
        try:
            return subprocess.run(
                *args,
                stdout=stdout if stdout else subprocess.PIPE,
                stderr=stderr if stderr else subprocess.PIPE,
                check=check,
                **kwargs,
            )
        except subprocess.CalledProcessError as ex:
            logger.debug(
                "Execution failed with code %d stdout=%r stderr=%r",
                ex.returncode,
                ex.stdout,
                ex.stderr,
            )
            raise

    return _run(*outer_args, **outer_kwargs)
