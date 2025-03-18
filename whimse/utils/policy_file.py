import bz2
from pathlib import Path


BZ2_MAGIC = b"BZh"

def read_policy_file(filename: str | Path) -> bytes:
    with open(filename, "rb")as file:
        data = file.read()
    if len(data) >= len(BZ2_MAGIC) and data[:len(BZ2_MAGIC)] == BZ2_MAGIC:
        data = bz2.decompress(data)
    return data
