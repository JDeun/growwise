from __future__ import annotations

from growwise.adapters.curriculum_watch import OfficialCurriculumUpdateWatcher


class StubHtmlClient:
    def __init__(self, *, ncic: str, moe: str) -> None:
        self.ncic = ncic
        self.moe = moe

    def get_text(
        self,
        url: str,
        *,
        params: dict[str, str | int | float],
        accept: str,
    ) -> str:
        del params, accept
        if "ncic." in url:
            return self.ncic
        return self.moe


def test_curriculum_watcher_ignores_known_official_revisions() -> None:
    watcher = OfficialCurriculumUpdateWatcher(
        http=StubHtmlClient(  # type: ignore[arg-type]
            ncic=(
                '<a href="/board/known">'
                "[국가교육위원회 고시 제2024-3호] "
                "(2022 개정 관련) 초·중등학교 교육과정 고시 안내"
                "</a>"
            ),
            moe='<a href="/known">2024 개정 표준보육과정(0~2세) 확정 발표</a>',
        )
    )

    assert watcher.check() == []


def test_curriculum_watcher_recognizes_current_2026_school_notice() -> None:
    watcher = OfficialCurriculumUpdateWatcher(
        http=StubHtmlClient(  # type: ignore[arg-type]
            ncic=(
                '<a href="/bbs/current">'
                "국가교육위원회 고시 제2026-1호 초중등학교 교육과정 고시"
                "</a>"
            ),
            moe="",
        )
    )

    assert watcher.check() == []


def test_curriculum_watcher_surfaces_unknown_revision_candidates() -> None:
    watcher = OfficialCurriculumUpdateWatcher(
        http=StubHtmlClient(  # type: ignore[arg-type]
            ncic=(
                '<a href="/board/new">'
                "[국가교육위원회 고시 제2028-7호] "
                "(2022 개정 관련) 초·중등학교 교육과정 고시 안내"
                "</a>"
            ),
            moe='<a href="/new">2029 개정 표준보육과정 확정 발표</a>',
        )
    )

    candidates = watcher.check()

    assert {(candidate.source, candidate.marker) for candidate in candidates} == {
        ("ncic", "국가교육위원회 고시 제2028-7호"),
        ("moe_early_childhood", "2029"),
    }
    assert all(candidate.url.startswith("https://") for candidate in candidates)
