from logging import Logger, DEBUG
from typing import Callable


def trace[
    **ParamsT, ReturnT
](
    logger: Logger,
    *,
    log_args: bool = True,
    log_ret: bool = True,
) -> Callable[
    [Callable[ParamsT, ReturnT]], Callable[ParamsT, ReturnT]
]:
    def decorator(func: Callable[ParamsT, ReturnT]) -> Callable[ParamsT, ReturnT]:
        name = func.__qualname__

        def wrapper(*args: ParamsT.args, **kwargs: ParamsT.kwargs) -> ReturnT:
            if log_args:
                logger.debug("%s enter args=%r kwargs=%r", name, args, kwargs)
            else:
                logger.debug("%s enter", name)
            try:
                retvalue = func(*args, **kwargs)
                if log_ret:
                    logger.debug("%s exit ret=%r", name, retvalue)
                else:
                    logger.debug("%s exit", name)
                return retvalue
            except Exception as ex:
                logger.debug("%s except %s", name, ex)
                raise

        return wrapper

    return decorator
