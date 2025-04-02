from collections.abc import Iterable


def either[
    T, DefaultT
](col: Iterable[T | None], default: DefaultT = None) -> T | DefaultT:
    try:
        return next(item for item in col if item is not None)
    except StopIteration:
        return default
