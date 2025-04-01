from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from whimse.types.local_modifications import SecurityContext

import auparse


@dataclass(frozen=True, kw_only=True)
class AVCEvent:
    text: str
    denied: bool
    perms: str
    scontext: SecurityContext
    tcontext: SecurityContext
    tcls: str
    permissive: bool


def get_avc_events(start_time: datetime | None) -> Iterable[AVCEvent]:
    auparser = auparse.AuParser(auparse.AUSOURCE_LOGS)
    auparser.search_add_item("type", "=", "AVC", auparse.AUSEARCH_RULE_CLEAR)
    if start_time:
        auparser.search_add_timestamp_item(
            ">=",
            int(start_time.timestamp()),
            start_time.microsecond // 1000,
            auparse.AUSEARCH_RULE_AND,
        )
    while auparser.search_next_event():
        assert auparser.find_field("seresult")
        text = auparser.get_record_text()
        auparser.first_field()
        result = auparser.find_field("seresult")
        auparser.first_field()
        perms = auparser.find_field("seperms")
        auparser.first_field()
        scontext = auparser.find_field("scontext")
        auparser.first_field()
        tcontext = auparser.find_field("tcontext")
        auparser.first_field()
        tcls = auparser.find_field("tclass")
        auparser.first_field()
        permissive = auparser.find_field("permissive")
        yield AVCEvent(
            text=text,
            denied=result == "denied",
            perms=perms,
            scontext=SecurityContext.parse(scontext),
            tcontext=SecurityContext.parse(tcontext),
            tcls=tcls,
            permissive=permissive == "1",
        )
