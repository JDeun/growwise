from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin

from .http import JsonHttpClient

_NCIC_URL = "https://ncic.go.kr/board/B0033.cs"
_MOE_EARLY_URL = "https://www.moe.go.kr/boardCnts/list.do"
_KNOWN_NCIC_NOTICES = frozenset(
    {
        "국가교육위원회 고시 제2024-1호",
        "국가교육위원회 고시 제2024-2호",
        "국가교육위원회 고시 제2024-3호",
        "국가교육위원회 고시 제2024-4호",
    }
)
_KNOWN_EARLY_REVISIONS = frozenset({"2024"})
_NCIC_NOTICE_RE = re.compile(r"국가교육위원회\s*고시\s*제\d{4}-\d+호")
_EARLY_REVISION_RE = re.compile(r"(20\d{2})\s*개정\s*표준보육과정")


@dataclass(frozen=True)
class CurriculumUpdateCandidate:
    source: str
    marker: str
    title: str
    url: str


class OfficialCurriculumUpdateWatcher:
    """Detect official curriculum revision candidates without auto-trusting scraped HTML."""

    def __init__(self, *, http: JsonHttpClient | None = None) -> None:
        self.http = http or JsonHttpClient(max_response_bytes=2_000_000)

    def check(self) -> list[CurriculumUpdateCandidate]:
        candidates = [
            *self._check_ncic(),
            *self._check_early_childhood(),
        ]
        unique: dict[tuple[str, str], CurriculumUpdateCandidate] = {}
        for candidate in candidates:
            unique[(candidate.source, candidate.marker)] = candidate
        return list(unique.values())

    def _check_ncic(self) -> list[CurriculumUpdateCandidate]:
        html = self.http.get_text(
            _NCIC_URL,
            params={"pageIndex": 1, "pageUnit": 30},
            accept="text/html,application/xhtml+xml",
        )
        anchors = _anchors(html, base_url=_NCIC_URL)
        candidates: list[CurriculumUpdateCandidate] = []
        for title, url in anchors:
            if "개정 관련" not in title or "교육과정 고시 안내" not in title:
                continue
            match = _NCIC_NOTICE_RE.search(title)
            if match is None:
                continue
            marker = " ".join(match.group(0).split())
            if marker in _KNOWN_NCIC_NOTICES:
                continue
            candidates.append(
                CurriculumUpdateCandidate(
                    source="ncic",
                    marker=marker,
                    title=title,
                    url=url,
                )
            )
        return candidates

    def _check_early_childhood(self) -> list[CurriculumUpdateCandidate]:
        html = self.http.get_text(
            _MOE_EARLY_URL,
            params={
                "boardID": 312,
                "m": "0301",
                "page": 1,
                "s": "moe",
                "searchType": "S",
            },
            accept="text/html,application/xhtml+xml",
        )
        anchors = _anchors(html, base_url=_MOE_EARLY_URL)
        candidates: list[CurriculumUpdateCandidate] = []
        for title, url in anchors:
            match = _EARLY_REVISION_RE.search(title)
            if match is None:
                continue
            marker = match.group(1)
            if marker in _KNOWN_EARLY_REVISIONS:
                continue
            candidates.append(
                CurriculumUpdateCandidate(
                    source="moe_early_childhood",
                    marker=marker,
                    title=title,
                    url=url,
                )
            )
        return candidates


class _AnchorParser(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.items: list[tuple[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "a":
            return
        self._href = dict(attrs).get("href")
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "a" or self._href is None:
            return
        title = " ".join(" ".join(self._parts).split())
        if title:
            self.items.append((title, urljoin(self.base_url, self._href)))
        self._href = None
        self._parts = []


def _anchors(html: str, *, base_url: str) -> list[tuple[str, str]]:
    parser = _AnchorParser(base_url=base_url)
    parser.feed(html)
    parser.close()
    return parser.items
