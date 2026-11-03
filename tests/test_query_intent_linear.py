from datetime import date
from time import perf_counter

import pytest

from growwise.services.conversation import _requests_material
from growwise.services.search import NaturalLanguageSearch


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("그 책으로 활동지를 만들어 주세요", True),
        ("자료를 준비해\n주세요", True),
        ("생성해줘. 그리고 카드는 어디 있지?", False),
        ("카드\n만들어줘", False),
        ("만들어줘\n이 책으로 자료를 생성해줄래", True),
        ("활동 자료 카드에 관한 기록", False),
    ],
)
def test_material_request_keeps_noun_before_verb_and_line_boundary(question, expected):
    assert _requests_material(question) is expected


@pytest.mark.parametrize(
    ("question", "order", "limit"),
    [
        ("최근 읽은 건 언제야", "newest", 1),
        ("언제 최근 읽었지", "newest", 8),
        ("처음 읽은 건 언제야", "oldest", 1),
        ("언제 처음 읽었지", "relevance", 8),
        ("처음\n언제", "relevance", 8),
        ("가장 처음 읽은 책", "oldest", 1),
        ("마지막으로 처음 읽은 건 언제야", "newest", 1),
    ],
)
def test_search_order_keeps_term_order_and_newest_priority(question, order, limit):
    plan = NaturalLanguageSearch.explicit_plan(question, 8, date(2026, 11, 3))
    assert (plan.order, plan.limit) == (order, limit)


def test_repeated_twenty_thousand_character_prefixes_complete_in_linear_time():
    started = perf_counter()
    for prefix in ("최근", "처음"):
        question = prefix * 10_000
        plan = NaturalLanguageSearch.explicit_plan(question, 8, date(2026, 11, 3))
        assert plan.limit == 8
    assert not _requests_material("자료" * 10_000 + "만들어")
    assert not _requests_material("활동" * 10_000 + "준비해")
    assert perf_counter() - started < 1.0
