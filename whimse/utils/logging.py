import logging as og_loggig
from typing import cast

DEBUG = og_loggig.DEBUG
INFO = og_loggig.INFO
VERBOSE = (INFO + DEBUG) // 2
og_loggig.addLevelName(VERBOSE, "VERBOSE")
WARNING = og_loggig.WARNING
ERROR = og_loggig.ERROR
CRITICAL = og_loggig.CRITICAL


class Logger(og_loggig.Logger):
    def verbose(self, msg: str, *args, **kwargs) -> None:
        return self.log(VERBOSE, msg, *args, **kwargs)


def get_logger(name: str) -> Logger:
    og_loggig.setLoggerClass(Logger)
    return cast(Logger, og_loggig.getLogger(name))
