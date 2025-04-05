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

import bz2
from logging import getLogger
from pathlib import Path

BZ2_MAGIC = b"BZh"

_logger = getLogger(__name__)


def read_policy_file(filename: str | Path) -> bytes:
    _logger.debug("Reading policy file %r", filename)
    with open(filename, "rb") as file:
        data = file.read()
    if len(data) >= len(BZ2_MAGIC) and data[: len(BZ2_MAGIC)] == BZ2_MAGIC:
        _logger.debug("Decompressing policy file %r", filename)
        data = bz2.decompress(data)
    return data
