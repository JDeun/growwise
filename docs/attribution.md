# 라이선스 귀속과 provenance

"상업-안전 라이선스만"([integrations.md](integrations.md))은 **자동으로 안전**하다는 뜻이
아니다. permissive라도 대부분 **귀속(attribution)** 의무가 있고, CC-BY-SA는 **파생물
상속** 의무가 있다. 이를 지키는 메커니즘을 정의한다.

## 라이선스 유형별 의무

- **무조건 자유(CC0/PD/BSD/MIT/Apache)** — 의무 최소. 코드/데이터: Wikidata, NASA,
  Openclipart, SymPy, Manim, Blockly, WordNet, CMUdict, whisper.cpp, MeloTTS, Tesseract,
  Typst, WeasyPrint 등. (Apache는 NOTICE 보존 권고.)
- **귀속 필요(CC-BY)** — **출력물에 출처 표기 의무**. StoryWeaver, PhET, Tatoeba,
  Illustrative Math 1판 등. 활동지에 이 소스를 쓰면 **그 활동지에 크레딧**을 넣어야 한다.
- **귀속 + 상속(CC-BY-SA)** — 귀속 + **파생 데이터도 동일 라이선스로 개방**. KRDict·
  우리말샘·Wiktextract·wordfreq 데이터. **미디어(발음 음성·이미지)는 오픈 아님(재배포 금지).**

## 메커니즘

1. **provenance 추적**: 각 `generated_material`에 **사용한 소스 목록**(id·라이선스)을 기록.
   생성 파이프라인이 어떤 데이터를 참조했는지 남긴다.
2. **출력물 귀속 자동 삽입**: CC-BY 소스를 쓴 활동지·카드에는 **하단 크레딧**(소스명·저작자·
   라이선스)을 자동 생성. 인쇄물에도 포함.
3. **NOTICE 파일**: 앱에 번들된 OSS·폰트·아이콘·데이터의 라이선스 목록을 담은 `NOTICE`/
   "정보" 화면 제공(Pretendard OFL, Lucide ISC, Apache 컴포넌트 등).
4. **BY-SA 격리**: BY-SA 유래 데이터는 **분리 보관**하고, 이를 가공해 재배포할 경우 파생물도
   BY-SA로 개방. 폐쇄형 상용 데이터와 **섞지 않는다**(오염 방지). 미디어 파일은 재배포하지
   않는다.
5. **비상업/독점은 애초 배제**([integrations.md](integrations.md) 9절 함정→대체).

## 상업/기관 확장 시

- 상업 배포 전 provenance·NOTICE·BY-SA 격리가 실제로 지켜지는지 감사한다.
- CC-BY 콘텐츠를 대량 포함하면 크레딧 관리 부담이 커지므로, **자체 제작 비중**을 높이는
  방향([integrations.md](integrations.md) 10절)이 라이선스 측면에서도 안전하다.
