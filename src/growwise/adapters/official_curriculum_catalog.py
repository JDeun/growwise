from __future__ import annotations

from collections.abc import Iterable

from .base import AdapterResult
from .curriculum import CurriculumRecord


class OfficialKoreanCurriculumCatalogAdapter:
    """Bundled metadata-only catalog of official Korean curriculum source pages.

    The catalog stores links, notice identifiers and high-level metadata only. It deliberately does
    not download or redistribute curriculum PDFs or source text, because individual documents may
    have reuse restrictions. No child/profile data is accepted by this adapter.
    """

    SOURCE = "kr_official_curriculum_catalog"
    ATTRIBUTION = "교육부·국가교육과정정보센터·i-누리 공식 교육과정 자료"
    LICENSE_NOTE = (
        "메타데이터·공식 링크만 제공. 원문·첨부파일의 이용조건은 제공기관 표시를 따르며 "
        "GrowWise는 원문을 재배포하지 않음"
    )

    _RECORDS: tuple[CurriculumRecord, ...] = (
        CurriculumRecord(
            curriculum_id="kr-childcare-2024-notice",
            title="2024 개정 표준보육과정(0~2세) 고시문",
            stage="infant_0_2",
            domain="신체운동·건강 / 의사소통 / 사회관계 / 예술경험 / 자연탐구",
            source_url=(
                "https://i-nuri.go.kr/teacher/board/view.do?"
                "board_idx=4332&data_type=normal&manage_idx=137&menu_idx=20"
            ),
            metadata={
                "provider": "교육부·i-누리",
                "official_notice": "교육부고시 제2024-23호",
                "document_type": "notice",
                "content_policy": "link_only",
            },
        ),
        CurriculumRecord(
            curriculum_id="kr-childcare-2024-guide",
            title="2024 개정 표준보육과정(0~2세) 해설서",
            stage="infant_0_2",
            source_url=(
                "https://i-nuri.go.kr/teacher/board/view.do?"
                "board_idx=4331&data_type=normal&manage_idx=137&menu_idx=20"
            ),
            metadata={
                "provider": "교육부·i-누리",
                "official_notice": "교육부고시 제2024-23호",
                "document_type": "guide",
                "content_policy": "link_only",
            },
        ),
        CurriculumRecord(
            curriculum_id="kr-childcare-2024-practice-0-1",
            title="2024 개정 표준보육과정(0~2세) 0~1세 실행자료",
            stage="infant_0_2",
            source_url=(
                "https://i-nuri.go.kr/teacher/board/view.do?"
                "board_idx=4330&data_type=normal&manage_idx=137&menu_idx=20"
            ),
            metadata={
                "provider": "교육부·i-누리",
                "official_notice": "교육부고시 제2024-23호",
                "document_type": "practice",
                "age_band": "0-1",
                "content_policy": "link_only",
            },
        ),
        CurriculumRecord(
            curriculum_id="kr-childcare-2024-practice-2",
            title="2024 개정 표준보육과정(0~2세) 2세 실행자료",
            stage="infant_0_2",
            source_url=(
                "https://i-nuri.go.kr/teacher/board/view.do?"
                "board_idx=4329&data_type=normal&manage_idx=137&menu_idx=20"
            ),
            metadata={
                "provider": "교육부·i-누리",
                "official_notice": "교육부고시 제2024-23호",
                "document_type": "practice",
                "age_band": "2",
                "content_policy": "link_only",
            },
        ),
        CurriculumRecord(
            curriculum_id="kr-nuri-2019-notice",
            title="2019 개정 누리과정 고시문 안내",
            stage="preschool_3_5",
            domain="신체운동·건강 / 의사소통 / 사회관계 / 예술경험 / 자연탐구",
            source_url=(
                "https://i-nuri.go.kr/teacher/board/view.do?"
                "board_idx=860&data_type=normal&manage_idx=24&menu_idx=19"
            ),
            metadata={
                "provider": "교육부·보건복지부·i-누리",
                "official_notice": "교육부고시 제2019-189호·보건복지부고시 제2019-152호",
                "document_type": "notice",
                "content_policy": "link_only",
            },
        ),
        CurriculumRecord(
            curriculum_id="kr-national-2022-elementary",
            title="초·중등학교 교육과정 2026 일부개정 고시 안내",
            stage="elementary",
            source_url=(
                "https://www.ne.go.kr/user/bbs/BD_selectBbs.do?"
                "q_bbsDocNo=20260121102419070&q_bbsSn=1016"
            ),
            metadata={
                "provider": "교육부·NCIC",
                "official_notice": "국가교육위원회고시 제2026-1호",
                "base_notice": "국가교육위원회고시 제2024-3호",
                "activation_policy": "grade_resolver",
                "document_type": "notice",
                "content_policy": "link_only",
            },
        ),
        CurriculumRecord(
            curriculum_id="kr-national-2022-middle",
            title="초·중등학교 교육과정 2026 일부개정 고시 안내",
            stage="middle",
            source_url=(
                "https://www.ne.go.kr/user/bbs/BD_selectBbs.do?"
                "q_bbsDocNo=20260121102419070&q_bbsSn=1016"
            ),
            metadata={
                "provider": "교육부·NCIC",
                "official_notice": "국가교육위원회고시 제2026-1호",
                "base_notice": "국가교육위원회고시 제2024-3호",
                "activation_policy": "grade_resolver",
                "document_type": "notice",
                "content_policy": "link_only",
            },
        ),
        CurriculumRecord(
            curriculum_id="kr-national-2022-high",
            title="초·중등학교 교육과정 2026 일부개정 고시 안내",
            stage="high",
            source_url=(
                "https://www.ne.go.kr/user/bbs/BD_selectBbs.do?"
                "q_bbsDocNo=20260121102419070&q_bbsSn=1016"
            ),
            metadata={
                "provider": "교육부·NCIC",
                "official_notice": "국가교육위원회고시 제2026-1호",
                "base_notice": "국가교육위원회고시 제2024-3호",
                "activation_policy": "grade_resolver",
                "document_type": "notice",
                "content_policy": "link_only",
            },
        ),
    )

    def search(
        self,
        *,
        stage: str,
        subject: str | None = None,
        query: str | None = None,
        offline: bool = False,
    ) -> AdapterResult:
        """Return bundled official-source metadata using the shared adapter contract.

        ``offline`` is accepted for API compatibility; the catalog is bundled and therefore works
        identically without network access.
        """
        del offline
        normalized_stage = " ".join(stage.split())
        normalized_subject = " ".join((subject or "").split()).casefold()
        normalized_query = " ".join((query or "").split()).casefold()
        if not normalized_stage or len(normalized_stage) > 100:
            raise ValueError("stage must be 1-100 characters")
        if len(normalized_subject) > 100:
            raise ValueError("subject must be at most 100 characters")
        if len(normalized_query) > 200:
            raise ValueError("query must be at most 200 characters")

        records = [record for record in self._RECORDS if record.stage == normalized_stage]
        if normalized_subject:
            subject_matches = [
                record for record in records if self._matches(record, normalized_subject)
            ]
            if subject_matches:
                records = subject_matches
        if normalized_query:
            query_matches = [
                record for record in records if self._matches(record, normalized_query)
            ]
            if query_matches:
                records = query_matches

        return AdapterResult(
            source=self.SOURCE,
            records=[record.model_dump(mode="json") for record in records],
            attribution=self.ATTRIBUTION,
            license_note=self.LICENSE_NOTE,
            cache_status="fresh",
        )

    @staticmethod
    def _matches(record: CurriculumRecord, needle: str) -> bool:
        values: Iterable[str | None] = (
            record.title,
            record.subject,
            record.domain,
            record.competency,
            str(record.metadata.get("official_notice", "")),
            str(record.metadata.get("document_type", "")),
        )
        return any(needle in (value or "").casefold() for value in values)
