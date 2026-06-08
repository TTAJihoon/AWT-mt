# data/assets — AWT 자산 저장소

자산은 **파일 기반**으로 저장되며, LLM 호출 시 입력 파라미터로 주입된다.
API 호출 자체는 stateless(D38 유지), 자산은 별도 영속 저장소.

## 디렉터리 구조

```
data/assets/
├── defect-catalog/           # 발견된 결함 + AI 생성 패턴 제안
│   ├── BOARD_CMS/            # 제품 유형별 분리 (Q4.2 결정)
│   ├── USER_AUTH/
│   ├── SHOPPING/
│   └── _schema.json          # 스키마 문서
├── domain-invariants/        # 제품 유형별 불변 규칙 (AI 자동 추출 + 누적)
│   ├── BOARD_CMS.yaml
│   └── USER_AUTH.yaml
├── cross-screen-invariants/  # 화면 간 일관성 규칙 (Phase 2)
├── test-patterns/            # 재사용 가능한 TestPattern (Phase 2)
└── equivalence-templates/    # 입력 유형별 등가류 템플릿 (Phase 2)
```

## 자산 생명주기

```
결함 발견
  → 테스터가 사실(제목/현상/기대) 기록
  → PATTERN_EXTRACT Contract가 patternProposal 자동 생성
  → 테스터가 승인/기각
  → 승인된 patternProposal의 suggestedInvariant → domain-invariants.yaml 추가 후보
  → 시험설계 리드 검토 후 yaml 반영
```

## 추적성

- 파일 내 `_meta` 블록: 누가 만들었고 누가 승인했는지
- PostgreSQL `awt_asset_events` 테이블: 승인/기각 이벤트 로그

## 제품 유형 ID

| ID | 설명 |
|---|---|
| BOARD_CMS | 게시판/CMS |
| USER_AUTH | 회원/인증/로그인 |
| SHOPPING | 쇼핑몰/전자상거래 |
| SEARCH | 검색 |
| DASHBOARD | 대시보드/분석 |
| FORM_WORKFLOW | 폼/워크플로우 |
| OTHER | 기타 |
