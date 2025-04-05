# Copyright (C) 2025 Juraj Marcin <juraj@jurajmarcin.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
