# PoC-β 진행 가이드

너가 *처음으로* reviewer 역할을 하는 거야.

---

## 👉 한 파일만 열어

**[output/tc_review.xlsx](output/tc_review.xlsx)** ← Excel에서 더블클릭

- 2개 시트: **`안내`** (먼저 읽기) + **`TC 검토`** (작업)
- 41개 TC × 14 컬럼 (시험소 표준 양식 그대로)
- 신뢰도 기반 색상: 🟢 회색 15개 / 🟡 노랑 18개 / 🔴 빨강 8개
- `결정` 컬럼은 **A/E/R/P 드롭다운** 자동 적용

---

## 진행 순서

1. **`안내` 시트** 먼저 — 컬럼 의미·기법·색상·결정 표시 방법 (1~2분)
2. **`TC 검토` 시트** — 41개 TC 검토. `결정` 컬럼에 A/E/R/P 드롭다운 선택. `검토 노트` 자유 기입.
   - 🟢 회색 15개 — 빠르게 [A] (약 2~5분)
   - 🟡 노랑 18개 — 천천히 (약 15~25분)
   - 🔴 빨강 8개 — 너의 판단이 가장 가치 (약 10~20분)
3. **저장** (Ctrl+S, 같은 위치)
4. **공유** — AWT에게 알리면 다음 PoC-γ 진행

---

## 막히면

- **결정 자체가 어려운 TC** → `P` (pending) + 검토 노트에 이유
- **AWT 추론이 무리해 보임** → `R` (rejected) + 사유 — *AWT의 약점 발견은 가치 있는 데이터*
- **매뉴얼 근거 확인하고 싶음** → [sample-board/input/manual.md](sample-board/input/manual.md)
- **board.html 실제 동작 보고 싶음** → 브라우저에서 열어 직접 만져보기 ([sample-board/board.html](sample-board/board.html))
- **부담스러우면 중도 종료 OK** — 부분 결과만 공유해도 충분

---

## 부가 자료 (선택)

| 파일 | 용도 |
|---|---|
| [output/tc_review.md](output/tc_review.md) | xlsx와 같은 내용의 마크다운 버전. xlsx가 안 열리거나 텍스트로 보고 싶을 때만. |
| [output/tc_raw.csv](output/tc_raw.csv) | 원본 CSV (UTF-8 BOM). 다른 도구로 가공할 때만. |
| [output/analysis.md](output/analysis.md) | AWT의 PoC-α 자체 평가 (V1~V5 검증 결과·BUG 검출 시도 등) |
| [output/v_meta.json](output/v_meta.json) | 메타 데이터 (분포·통계) |

> **xlsx가 1차 산출물**, 위는 모두 보조 자료.

---

## 결과 양식 (검토 종료 후 알려줘)

채팅으로 한 줄씩 알려줘도 OK, 별도 파일로 정리해도 OK:

```
- 결정 분포: approved __개 / edited __개 / rejected __개 / pending __개
- 총 소요 시간: __분
- 피로도 (1~5): __
- 가장 판단 어려웠던 TC: TC-___-___ (이유)
- AWT가 다음에 개선했으면: ___
- 종합 판단: 다음 PoC-γ로 진행 OK? Y/N
```

---

## 너의 시각을 *솔직히*

이건 평가가 아니야. *AWT가 너의 작업에 진짜 쓸 만한지* 솔직한 판단이 PoC-β의 본질.

3가지 결론 모두 의미 있어:
- "쓸 만하다" → PoC-γ로
- "TC 품질이 부족하다" → 어디가 부족한지 알려주면 prompt 조정
- "검토가 부담스럽다" → Gate UX 재설계
