"""Conservative rejection of explicit infant play hazards; this is not toy certification."""

from __future__ import annotations

import re

_CLAUSES = re.compile(r"[.!?;\n]+")
_MOUTH_ACTION = re.compile(
    r"입(?:\s*안|속)?(?:에|으로).{0,20}?"
    r"(?:가져가|넣|물(?=지|고|거나|도록|게|어)|빨(?=지|고|거나|도록|게|아))"
)
_PROTECTIVE_MOUTH_TAIL = re.compile(
    r"^(?:지\s*(?:않|말|마|못)|"
    r"(?:게|도록)\s*(?:유도|권|허용)?(?:하지|두지)\s*(?:않|말|마|못)|"
    r"(?:으)?려(?:고)?\s*(?:하면|할\s*때).{0,24}(?:치우|치워|빼|꺼내|제거|중단|막)|"
    r"(?:으)?면\s*(?:안|치우|치워|빼|꺼내|제거|중단)|"
    r"(?:는|기)\s*(?:것|행동)?(?:을|를)?\s*(?:막|금지))"
)
_HAZARD = re.compile(
    r"작은\s*(?:공(?!간)|구슬|물건|부품)|분리\s*부품|단추|동전|배터리|자석|풍선|비닐봉지|끈|리본"
)
_PROTECTIVE_USE = re.compile(
    r"(?:사용|제공)하지\s*(?:않|말|못)|쓰지\s*(?:않|말|못)|"
    r"피하|피합|치우|치워|치웁|제거|금지|닿지\s*않|없도록|사용\s*불가"
)
_ENGLISH_MOUTH = re.compile(
    r"(?:put|place).{0,35}(?:in|into)\s+.{0,20}?\bmouth\b|"
    r"(?:chew|suck)\s+(?:on\s+)?(?:the\s+)?(?:object|toy|block|material)", re.I,
)


def unsafe_infant_directions(text: str) -> bool:
    for clause in _CLAUSES.split(text):
        for match in _MOUTH_ACTION.finditer(clause):
            if not _PROTECTIVE_MOUTH_TAIL.match(clause[match.end():]):
                return True
        for match in _HAZARD.finditer(clause):
            after = clause[match.end():match.end() + 12]
            if re.match(r"(?:이|가|은|는)?\s*없", after):
                continue
            protection = _PROTECTIVE_USE.search(clause, match.end())
            preceding = clause[match.end():protection.start()] if protection else ""
            positive_action = re.search(
                r"쥐여|건네|굴리|만지게|놓아|주어|준비하|가지고\s*놀|사용하|제공하", preceding,
            )
            if protection is None or positive_action is not None:
                return True
        for match in _ENGLISH_MOUTH.finditer(clause):
            before = clause[max(0, match.start() - 35):match.start()].casefold()
            if not re.search(r"(?:do\s+not|never|avoid|prevent|stop).{0,25}$", before):
                return True
    return False
