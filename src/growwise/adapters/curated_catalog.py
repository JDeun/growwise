from __future__ import annotations

from .base import AdapterResult

_CURATED: tuple[dict[str, object], ...] = (
    {
        "id": "storyweaver",
        "title": "Pratham StoryWeaver",
        "summary": "한국어를 포함한 다국어 그림책과 읽기 수준별 공개 도서 플랫폼",
        "source_url": "https://storyweaver.org.in/",
        "topics": {"독서", "읽기", "문학", "언어", "영어"},
        "tags": ["그림책", "읽기", "다국어"],
        "license_note": "플랫폼의 CC BY 4.0 콘텐츠를 개별 도서 조건과 함께 확인",
    },
    {
        "id": "global-digital-library",
        "title": "Global Digital Library",
        "summary": "초기 문해력과 다국어 아동 도서를 탐색할 수 있는 공개 디지털 도서관",
        "source_url": "https://digitallibrary.io/",
        "topics": {"독서", "읽기", "문학", "언어"},
        "tags": ["그림책", "읽기", "다국어"],
        "license_note": "개별 도서 라이선스를 확인하고 commercial-safe 콘텐츠만 채택",
    },
    {
        "id": "phet",
        "title": "PhET Interactive Simulations",
        "summary": "과학·수학 개념을 직접 조작하고 관찰할 수 있는 인터랙티브 시뮬레이션",
        "source_url": "https://phet.colorado.edu/",
        "topics": {"과학", "실험", "물", "빛", "소리", "자석", "힘", "에너지", "수학"},
        "tags": ["시뮬레이션", "과학", "수학"],
        "license_note": "PhET 이용·라이선스 정책과 개별 시뮬레이션 조건을 확인",
    },
    {
        "id": "openstax",
        "title": "OpenStax",
        "summary": "공개 라이선스 기반 교과형 학습 자료와 설명 콘텐츠",
        "source_url": "https://openstax.org/",
        "topics": {"수학", "과학", "물", "에너지", "통계"},
        "tags": ["교과", "수학", "과학"],
        "license_note": "개별 교재의 Creative Commons 라이선스와 귀속 조건을 확인",
    },
    {
        "id": "khan-academy-kids",
        "title": "Khan Academy Kids",
        "summary": "유아·초기 학습자를 위한 읽기·수학·기초 학습 활동 참고 플랫폼",
        "source_url": "https://learn.khanacademy.org/khan-academy-kids/",
        "topics": {"읽기", "독서", "수학", "숫자", "모양", "색깔"},
        "tags": ["유아", "읽기", "수학"],
        "license_note": "링크/아이디어 참고용; 콘텐츠 재배포 권리는 별도 확인",
    },
    {
        "id": "nasa-kids-club",
        "title": "NASA Kids' Club",
        "summary": "우주·지구과학 주제를 어린이 활동으로 연결할 때 참고하는 NASA 교육 포털",
        "source_url": "https://www.nasa.gov/learning-resources/nasa-kids-club/",
        "topics": {"우주", "별", "달", "지구", "과학"},
        "tags": ["NASA", "우주", "어린이"],
        "license_note": "NASA 웹 콘텐츠 및 제3자 자료의 개별 이용 조건을 확인",
    },
)


class CuratedEducationCatalogAdapter:
    SOURCE = "curated_education_catalog"
    ATTRIBUTION = "GrowWise curated official education links"
    LICENSE_NOTE = "링크 카탈로그이며 실제 콘텐츠 재사용 전 원 출처의 개별 라이선스를 확인"

    def search(self, *, terms: list[str]) -> AdapterResult:
        selected: list[dict[str, object]] = []
        term_set = set(terms)
        for record in _CURATED:
            topics = record.get("topics")
            if not isinstance(topics, set) or not term_set.intersection(topics):
                continue
            selected.append(
                {
                    key: value
                    for key, value in record.items()
                    if key != "topics"
                }
            )
        return AdapterResult(
            source=self.SOURCE,
            records=selected,
            attribution=self.ATTRIBUTION,
            license_note=self.LICENSE_NOTE,
            cache_status="live",
        )
