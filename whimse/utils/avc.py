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

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import auparse

from whimse.types.local_modifications import SecurityContext


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
