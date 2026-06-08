# 05-deployable-skills/ — 별도 배포 가능한 sub-skill 카탈로그

AWT 프로젝트 외부에도 **독립적으로 가치 있는** 기능들을 식별해 Claude Skill로 패키징할 후보 목록.

## 의도

- **AWT 본체**는 시험소 내부 도구 (최상위 `SKILL.md`).
- 그러나 AWT가 만들어내는 도구들 중 **다른 조직/맥락에서도 쓸 만한 것**은 분리해 별도 Skill로 배포.
- 시험소의 R&D 결과물이 외부에 가치 전달 + 내부 강화 루프 형성.

## 파일

- `candidates.md` — 분리 배포 후보 sub-skill 목록과 각각의 독립성·재사용성 평가

## 분리 배포 기준

후보가 다음을 만족하면 분리 배포 가능:
1. **자기 완결성** — AWT 본체 없이 단독 사용 가능
2. **일반성** — SW 시험 도메인 외에도 적용 가능
3. **명확한 trigger** — 사용자 의도가 분명히 식별됨
4. **기밀 비의존** — 시험소 내부 데이터 없이 동작

## 1차 후보 (4인 토론에서 식별됨)

| 후보 | 핵심 기능 | 분리 적합성 |
|---|---|---|
| `web-dom-scanner` | URL → 구조화된 DOM + 이미지 스캔 | 매우 높음 |
| `manual-to-feature-list` | 매뉴얼 PDF/DOCX → 정규화 기능리스트 | 높음 |
| `tc-traceability-validator` | TC 산출물의 source_quote 검증 (grep-based) | 매우 높음 |
| `anonymizer-for-defects` | 결함 이력 익명화 파이프라인 | 중간 (도메인 의존) |
| `axe-accessibility-runner` | 접근성 자동 검사 wrapper + 보고서 | 높음 |
| `mutation-score-runner` | 임의 TC 집합의 mutation score 측정 | 중간 |

각 후보의 상세 검토는 `candidates.md`에서.
