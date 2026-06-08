# Sample Board — PoC 입력 패키지

**합성일:** 2026-05-19
**목적:** AWT의 standalone PoC-α/β/γ를 위한 *완전 통제된* 입력 자료 세트.

## 구성

```
sample-board/
├─ board.html                # 미니 게시판 mockup (단일 HTML, JS 인라인)
├─ input/
│  ├─ manual.md              # 한국어 사용자 매뉴얼 (v1.0)
│  ├─ feature-list.csv       # 대/중/소 분류 기능리스트 (10 leaf)
│  ├─ defect-samples.md      # 품질특성별 결함 패턴
│  └─ url.txt                # 시험 대상 URL (file://)
└─ README.md
```

## 기능 leaf 10개

회원관리·인증 (로그인, 로그아웃) + 게시글관리·작성/조회/수정/삭제 + 댓글관리·작성/삭제

## 의도적 함정 (PoC가 잡아야 할 것)

board.html에는 매뉴얼과 어긋나는 **3개의 의도된 결함**:

| ID | 위치 | 매뉴얼 | 실제 mockup | AWT가 잡아야 할 기법 |
|---|---|---|---|---|
| BUG-1 | 페이지네이션 | 마지막 페이지 정상 표시 | 범위 초과 시 빈 페이지 / 깨짐 | boundary (페이지 0, 1, max, max+1) |
| BUG-2 | 글 수정·삭제 | 작성자만 가능 | 모든 사용자(비로그인 포함)가 가능 | negative_deep (권한 우회 — 결함 샘플 F-2 직접 매칭) |
| BUG-3 | 글 제목 길이 | "적절한 길이" (매뉴얼 §3.1) | 길이 검증 없음 | boundary (1자, 50자, 51자, 빈 문자열) |

추가 *모호함* (AWT가 어떻게 해석할지 관찰):
- 매뉴얼 §3.1 "제목은 적절한 길이로" — *정확한 숫자 없음* → AWT가 INFERRED를 만들지, 결함 샘플 F-1을 참조해 추론할지

## PoC-α 진입

1. AWT skill 호출 (skill 구현 단계 후):
   ```
   /awt
   input_folder: data/poc/2026-05-19/sample-board/input/
   url: (input/url.txt 참조)
   ```
2. AWT가 Stage 1~3 수행 → `data/poc/2026-05-19/output/tc_verified.xlsx`
3. 사용자가 결과 검토 → `data/poc/2026-05-19/result.md`

## 사전 검증 — *AWT skill 본체가 아직 없을 때*

AWT skill 구현 전이라도, Claude Code에 다음 prompt를 *직접* 입력해 Stage 1·2·3을 시뮬레이션 가능:

```
[AWT PoC-α 수동 시뮬레이션]
다음 입력으로 TC를 생성해줘:
- 매뉴얼: data/poc/2026-05-19/sample-board/input/manual.md
- 기능리스트: data/poc/2026-05-19/sample-board/input/feature-list.csv
- 결함 샘플: data/poc/2026-05-19/sample-board/input/defect-samples.md
- 대상 URL: file:// (input/url.txt)

[강화 출력 요구]
모든 TC는 반드시 다음 컬럼 포함:
  tc_id, requirement_id (대>중>소 경로), design_technique, precondition, steps, expected, source_quote, oracle_reason, gen_confidence

design_technique: happy_path / equivalence / boundary / negative_basic / negative_deep / state_transition / cross_feature

각 leaf 기능마다:
  - happy_path 1개
  - 입력 도메인 2+ 있으면 equivalence
  - 수치·길이 제약 있으면 boundary 양쪽
  - negative_basic 1개+
  - negative_deep 1개+ (특히 권한·에러 메시지 4축)
  - 다단계면 state_transition
  - 의미 연관 다른 기능과 cross_feature 1개+

source_quote: 매뉴얼/기능리스트의 원문 그대로 발췌 + 위치 (예: "manual.md §3.1 '제목은 적절한 길이로'")
추론이면 "INFERRED: <근거 한 줄>"

TC ID: TC-XXX-YYY (XXX는 leaf 일련번호 1~10, YYY는 변형 번호, 둘 다 3자리)
gen_confidence: 0.0~1.0 (source_quote 명료성·기능 명세 강도)

산출: Excel 또는 CSV. PoC 검토용.
```

위 prompt를 Claude Code에 던지면, *AWT skill 본체 없이도* Stage 2 결과의 1차 형태가 나옴.

## 다음

- 사용자가 board.html을 브라우저에서 열어 동작 확인
- 사용자가 위 prompt로 PoC-α 수동 실행 → 결과 검토
- 결과를 `../result.md` 양식에 채워 공유 → 다음 턴 분석
