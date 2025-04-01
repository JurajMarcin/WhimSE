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
