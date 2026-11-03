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


## 설치 패키지에 포함하는 라이선스 원문

루트 `THIRD_PARTY_NOTICES.md`는 의존성 식별/링크 목록이며 원문 license를 대신하지 않는다.
`desktop/scripts/build_license_bundle.py`는 빌드 환경의 실제 Python runtime graph와 dependency
extra/platform marker를 따라 LICENSE·NOTICE·COPYRIGHT 등을 바이트 그대로 복사한다. Pillow의
wheel LICENSE에 포함된 이미지 라이브러리 저작권과 조건, requests의 Apache NOTICE도 보존한다.
Python interpreter와 PyInstaller bootloader/runtime-hook의 제공된 license/exception 원문은 별도
범주로 기록한다. 개발 도구가 설치된 환경에서 Core 실행 파일을 만들면 실패한다.

패키징 interpreter는 uv-managed Python3.12.13, python-build-standalone20260623으로 고정한다.
해당 배포자의 commit-pinned OpenSSL·libffi·liblzma·bzip2·expat·mpdecimal·SQLite·zlib
고지문과 실제 OpenSSL3.5.7의 LICENSE/AUTHORS 원문도 보존한다. 정적으로 interpreter에
들어간 구성요소를 빠뜨리지 않도록 배포자의 플랫폼 공통 고지문을 보수적으로 포함하며,
모든 구성요소가 매 실행에서 로드된다는 뜻은 아니다. 다른 interpreter build는 고지문을
다시 검토하기 전까지 패키징을 거절한다.
uv의 버전별 기본 카탈로그는 같은 Python patch 버전에도 다른 배포 빌드를 선택할 수 있다.
따라서 CI는 별도 설치 경로에서 commit-pinned 공식 download metadata의 URL과 archive
checksum을 사용해 해당 배포물을 먼저 설치한다. 사용한 metadata commit도 provenance에 남긴다.

production Node graph와 현재 host의 native Cargo graph도 로컬 설치 source의 원문을 동봉한다.
파일은 Tauri resources의 `licenses/`에 들어가며 `INDEX.md`로 찾고 `manifest.json`에서 package
버전·source provenance·SHA-256을 확인한다. 생성 결과는 플랫폼별 artifact이며 커밋하지 않는다.

공식 wheel/crate에서 원문을 생략한 경우 임의 저작권 문구나 generic license로 대체하지 않는다.
`assets/licenses/`에 해당 버전의 공식 repository commit에서 받은 원문과 출처/해시를 함께
검토·보존하며, 일치하는 override가 없거나 파일이 변조되면 패키징을 거절한다. 이 경로는
Python의 langchain-text-splitters1.1.2, langsmith0.12.4와 sqlite-vec0.1.9를 포함한다.
Git 속성은 override 원문의 바이트가 Windows checkout에서 변하지 않도록 고정한다.

Core build는 라이선스 묶음을 만들고 검증한 뒤 실행 파일을 만든다. package CI도 묶음의 해시와
runtime inventory를 다시 검증한다. 이는 제공된 원문과 provenance의 기술적 보존이며, 외부
데이터·모델 가중치·OS 구성요소의 별도 배포 조건을 모두 대체하는 법률 판정은 아니다.
