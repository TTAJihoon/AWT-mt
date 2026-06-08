# ISO/IEC 25010/25023/25051/25059 × Layer 자동화 가능성 매트릭스

**작성일:** 2026-05-18
**근거 결정:** D2(자동화 가능 영역 우선), D8(25023+25051 즉시 적용), D15(25059 AI 제품 한정 조건부)
**목적:** 시험소 내부 공식 입장 — *각 품질특성·메트릭에 대해 AWT가 어디까지 자동화할 수 있고, 시험원이 어디를 책임지는가*.

> **검수 필요:** 본 매트릭스는 AWT가 보유한 표준 지식 기반으로 작성. 시험소가 보유한 25023:2016, 25051:2014, 25059:2023 원본과 메트릭 ID/공식이 *완전 일치하는지 사용자 검수* 후 확정.

---

## 1. Layer 분류 정의 (Recap)

| Layer | 의미 | 책임 주체 | TC 처리 |
|---|---|---|---|
| **L1** | AWT 자동 (생성 + 실행 + 판정) | AWT | confidence 기반 자동 승인 후 Gate에서 빠른 확인 |
| **L2** | AWT 보조 + 시험원 검토 | AWT + 시험원 | Gate에서 인간이 모든 항목 검토 후 결정 |
| **L3** | 시험원 전담 | 시험원 (AWT 미관여) | 별도 워크플로, AWT는 *유관 정보만* 정리 제공 |

판정 기준 (재명시):
1. 메트릭이 객관적 기준으로 측정 가능 (인간 인지 불요)
2. Oracle을 명세에서 도출 가능
3. False PASS/FAIL 위험이 confidence로 정량화 가능
4. 재현성·추적성 강제 가능

위 4조건 모두 충족 → L1. 하나라도 미충족 → L2 또는 L3.

---

## 2. ISO/IEC 25010 × 25023 마스터 매트릭스

### 2.1. Functional Suitability (기능적 적합성)

| 부특성 | 25023 메트릭 (대표) | AWT 자동 측정 | Layer | 비고 |
|---|---|---|---|---|
| Functional completeness | 명세된 기능 중 구현된 기능 비율 | ✓ | **L1** | 기능리스트 vs TC 매핑으로 직접 계산 |
| Functional correctness | 기대값과 실제값 일치율 | ✓ | **L1** | TC 실행 결과의 PASS 비율 |
| Functional appropriateness | 사용 목적 달성을 위한 기능 적절성 | ◐ | **L2** | 적절성 판단에 도메인 지식 필요 |

> 4인 토론 결론: 요구사항·기능 커버리지는 AI 강점. 단 *3계층 커버리지 모델*(요구사항/입력도메인/시나리오) 중 시나리오는 L1만으로 부족 → cross_feature TC 강제(E2)로 보강.

### 2.2. Performance Efficiency (성능 효율성)

| 부특성 | 25023 메트릭 (대표) | AWT 자동 측정 | Layer | 비고 |
|---|---|---|---|---|
| Time behavior | 응답시간, 처리시간 | ✓ | **L1** | Playwright 타이밍 측정 가능 |
| Resource utilization | CPU·메모리·네트워크 | ◐ | **L2** | 브라우저 측 자원만 측정 가능. 서버 자원은 외부 모니터링 필요 |
| Capacity | 동시 사용자, 데이터량 | ✗ | **L3** | 부하시험 도구 별도 필요 (k6, Locust). Phase 2+ |

### 2.3. Compatibility (호환성)

| 부특성 | 25023 메트릭 (대표) | AWT 자동 측정 | Layer | 비고 |
|---|---|---|---|---|
| Co-existence | 다른 SW와 공존 시 영향 | ✗ | **L3** | 환경 셋업 필요 |
| Interoperability | 외부 시스템 연동 | ◐ | **L2** | API mock으로 일부 자동, 실거래는 L3 |
| (웹) 브라우저 호환성 | 주요 브라우저별 정상 동작 | ✓ | **L1** | Playwright multi-browser |

### 2.4. Usability (사용성) — *주요 자동화 한계 영역*

| 부특성 | 25023 메트릭 (대표) | AWT 자동 측정 | Layer | 비고 |
|---|---|---|---|---|
| Appropriateness recognizability | 사용자가 적합성 인지 가능성 | ✗ | **L3** | 인간 인지 정의상 필수 |
| Learnability | 학습 용이성 | ✗ | **L3** | SUS·USE 등 표준 설문 |
| Operability | 조작 용이성 | ◐ | **L2** | 일부 UX heuristic 자동 (탭 순서, 키보드 접근), 종합 평가는 L3 |
| User error protection | 오입력 방지·복구 안내 | ◐ | **L2** | negative_basic은 L1, negative_deep(메시지 적절성)은 L2 |
| User interface aesthetics | UI 미적 적합성 | ✗ | **L3** | 의도된 디자인 vs 버그 구분 불가 |
| Accessibility | WCAG 준수 | ◐ | **L2** | axe-core류로 30~40% 검출, 나머지(스크린리더·키보드 only 실사용)는 L3 |

> 4인 토론 결론: 사용성은 *25023 측정의 operational definition* 자체가 인간 panel/설문 요구. AWT는 *증거 자료 수집*까지만 자동화하고 평가는 시험원.

### 2.5. Reliability (신뢰성)

| 부특성 | 25023 메트릭 (대표) | AWT 자동 측정 | Layer | 비고 |
|---|---|---|---|---|
| Maturity | 결함 밀도 | ✓ | **L1** | TC FAIL 수 / TC 총 수 |
| Availability | 가동률 | ◐ | **L2** | 단시간 측정만 L1 가능. SLA는 장기 |
| Fault tolerance | 결함 발생 시 거동 | ◐ | **L2** | 의도된 결함 주입 TC (negative_deep)로 일부 |
| Recoverability | 복구 시간·완전성 | ◐ | **L2** | 시나리오 가능하나 복구의 *완전성*은 인간 판단 |

### 2.6. Security (보안) — *별도 표준 필요 영역*

| 부특성 | 25023 메트릭 (대표) | AWT 자동 측정 | Layer | 비고 |
|---|---|---|---|---|
| Confidentiality | 권한 없는 접근 차단 | ◐ | **L2** | IDOR 기초 자동, 심층은 L3 |
| Integrity | 무단 수정 방지 | ◐ | **L2** | 동일 |
| Non-repudiation | 부인 방지 (로그·서명) | ✗ | **L3** | 로그 정책 평가 |
| Accountability | 사용자 추적 가능성 | ✗ | **L3** | 감사 로그 검토 |
| Authenticity | 인증 정확성 | ◐ | **L2** | 로그인 시나리오는 L1, 정책 평가는 L3 |

> 보안은 OWASP·ISO 27001 등 별도 표준 영역. AWT는 *기초 자동 점검*만 제공하고 심층은 시험원·보안 전문가 협업.

### 2.7. Maintainability (유지보수성) — *대부분 정적 분석 영역*

| 부특성 | 25023 메트릭 (대표) | AWT 자동 측정 | Layer | 비고 |
|---|---|---|---|---|
| Modularity, Reusability, Analyzability, Modifiability | 소스 구조 메트릭 | ✗ | **L3 (또는 N/A)** | 소스 접근 가능 시 SonarQube 류. **웹 시험에서는 보통 N/A** (블랙박스) |
| Testability | 시험 용이성 | ◐ | **L2** | AWT의 *자체 메트릭*으로 부분 도출 (어떤 기능이 자동화 어려웠는지) |

### 2.8. Portability (이식성)

| 부특성 | 25023 메트릭 (대표) | AWT 자동 측정 | Layer | 비고 |
|---|---|---|---|---|
| Adaptability | 다양한 환경 적응성 | ◐ | **L2** | 브라우저·디바이스별 시험은 L1. 환경 변경은 L3 |
| Installability | 설치 용이성 | ✗ | **L3** | 웹은 보통 N/A |
| Replaceability | 다른 SW로 교체 용이성 | ✗ | **L3** | 평가 도메인 |

---

## 3. ISO/IEC 25051:2014 (RUSP/COTS) 추가 요구

25051은 *측정* 표준이 아니라 *상용 SW 제품의 품질 요구* 표준. 제품 자체 + 동반 문서의 품질을 함께 평가.

| 영역 | 요구 사항 | AWT 자동 측정 | Layer |
|---|---|---|---|
| 제품 설명서 (제품 정보) | 제품명·버전·기능 설명·요구 환경 명시 | ◐ | **L2** — AI가 매뉴얼에서 항목 존재 확인은 가능, 완전성·정확성 판단은 시험원 |
| 사용자 문서 | 설치·운영·문제해결 안내 | ◐ | **L2** |
| 제품 품질 | 25010 기반 시험 통과 | (25010 위 표 따름) | 위 §2 그대로 |
| 사용 시 품질 | 실사용 환경에서의 효과·효율·만족도 | ✗ | **L3** |
| 시험 문서 | 시험 절차·결과 기록 | ✓ | **L1** — *AWT가 산출하는 결과물 자체가 시험 문서*. 이 메트릭은 AWT의 *자기 산출 품질* |

> **시험소 운영의 핵심:** 25051은 한국 SW 시험인증에서 자주 적용되는 표준. *제품 설명서·사용자 문서의 정합성 검토*가 차지하는 비중이 큼 → L2 워크플로의 핵심 작업 중 하나.

---

## 4. ISO/IEC 25059:2023 (AI 시스템) — 조건부 적용 (D15)

> **적용 조건:** 대상 제품이 AI 기능을 *주된 기능*으로 포함할 때만 본 §4의 추가 메트릭을 적용. 비AI 제품은 §2·§3만으로 충분.

### 4.1. 25010 기존 특성의 AI 맥락 재정의

| 기존 부특성 | AI 맥락에서의 변화 | AWT 대응 | Layer |
|---|---|---|---|
| Functional correctness | 비결정적 출력 → 단일 PASS/FAIL 불가. **분포 기반 평가** 필요 | TC 스키마 확장: N회 반복 + 통계적 판정 (Phase 3) | **L2** (현재) → L1 (확장 후) |
| Reliability (Maturity) | 재학습 시 성능 변화 | 모델 버전 메타데이터 기록 강제 | **L2** |

### 4.2. AI 특화 신규 특성

| 부특성 | 의미 | AWT 자동 측정 | Layer | 비고 |
|---|---|---|---|---|
| **Functional adaptability** | 새 입력·맥락에 적응하는 정도 | ◐ | **L2** | metamorphic relation 시험으로 일부 자동 가능 |
| **User controllability** | 사용자가 AI 동작에 개입·조정 가능성 | ◐ | **L2** | "정지/되돌리기/조정" UI 존재 확인은 L1, 효과성은 L3 |
| **Transparency** | AI 결정 근거·과정 공개 정도 | ◐ | **L2** | "설명 표시 존재" L1, *설명 품질*은 L3 |
| **Robustness** | adversarial 입력에 대한 견고성 | ◐ | **L2** | 입력 변조 TC 자동 생성 가능, 평가는 L2 |
| **Intervenability** | 시스템 동작 중단·우회 가능성 | ◐ | **L2** | "kill switch" 존재 L1, 운영 절차는 L3 |

> 25059 도입 시점은 **AI 포함 제품이 전체의 20% 이상**일 때로 4인 토론에서 제시 (D 발언). 시험소 사용자가 *이미 AI 제품 비중 증가 추세 인지*하고 있어 Phase 2 진입 시점에 본격 도입.

### 4.3. TC 스키마 영향

25059 적용 시 TC에 다음 컬럼이 *옵션*으로 추가됨 (`doc/04-tc-design-spec/01-tc-schema.md` 후속 보강):
- `ai_repetition_count` — 반복 시행 횟수 (분포 기반 평가용)
- `ai_pass_rate` — N회 중 PASS 비율
- `ai_model_version` — 시험 대상 AI 모델 식별
- `ai_input_variation` — metamorphic 시험 시 입력 변환 종류

---

## 5. Layer별 통합 요약

### Layer 1 (AWT 자동) — 1차 전수 시험

가장 비중 큰 영역. AWT가 책임:
- Functional Suitability 거의 전부
- Performance Time behavior
- 웹 브라우저 호환성
- Reliability Maturity
- 25051 시험 문서 자체 산출

→ **시험소 처리량 증가의 70~80%가 여기서 발생할 것으로 추정.**

### Layer 2 (AWT 보조 + 시험원 검토)

AWT가 *증거 자료를 정리해주면 시험원이 판정*:
- Functional appropriateness (도메인 적절성)
- Operability·User error protection·Accessibility (UX 일부)
- Resource utilization·Fault tolerance·Recoverability
- Security 기초 (IDOR·인증)
- 25051 제품 설명서·사용자 문서 정합성
- 25059 AI 특화 5종 거의 전부

→ **시험원의 핵심 작업 영역.** AWT는 *검토 시간 단축 도구* 역할.

### Layer 3 (시험원 전담) — AWT 미관여

정의상 자동화 불가:
- Usability Recognizability·Learnability·Aesthetics
- Capacity (부하)
- Security 심층 (별도 표준)
- Maintainability 소스 메트릭 (블랙박스에서 N/A)
- Portability Replaceability

→ **AWT는 관련 정보 정리만 제공.** 평가는 시험원.

---

## 6. AWT가 *측정해야 하는데 현재 안 하는 것* (D21 시사점)

사용자 인터뷰에서 *25023 메트릭 % 자체를 측정하지 않는다*고 확인됨 (D21). 그러나 위 매트릭스에서 L1로 분류된 항목들은 *AWT가 자동 측정 가능*:

| 메트릭 | 자동 계산 가능 | Phase | 산출 위치 |
|---|---|---|---|
| Functional completeness % | ✓ | Phase 2 | 결함 리포트 보강 |
| Functional correctness % | ✓ | Phase 2 | 결함 리포트 보강 |
| Time behavior (response time 분포) | ✓ | Phase 2 | 별도 시트 |
| Maturity (defect density) | ✓ | Phase 2 | 결함 리포트 보강 |

> **AWT의 Phase 2 주요 가치:** 시험소가 현재 측정 안 하는 메트릭 %들을 *자동 산출해 내부 KPI로 제공*. 외부 보고서 포함 여부는 Phase 2 시점에 별도 결정.

---

## 7. 후속 문서 안내

본 매트릭스의 각 Layer별 상세는 다음 문서에서 다룬다 (`doc/02-iso-25023-mapping/` 폴더):

- **`02-automatable.md`** — Layer 1 상세 (메트릭별 입력/처리/출력)
- **`03-semi-automatable.md`** — Layer 2 상세 (AWT 보조 범위 + 시험원 결정 가이드)
- **`04-human-only.md`** — Layer 3 상세 (AWT가 제공 가능한 보조 정보)
- **`05-curation-workflow.md`** — Layer 2 Gate에서 시험원이 수행하는 작업 절차
- **`06-deep-areas.md`** — Layer 3 심층 시험 절차
- **`07-exploratory-charter.md`** — 탐색적 시험 charter 양식
- **`08-metric-definitions.md`** — 각 메트릭의 정확한 계산식 (operational definition) — 25023 원본 검수 필요

---

## 8. 미해결 (검수 후 답변 부탁)

| ID | 항목 | 영향 |
|---|---|---|
| Q-MX-1 | 위 §2 매트릭스의 메트릭 분류·Layer 판정이 시험소 실무와 일치하는가 | 매트릭스 정합성 |
| Q-MX-2 | 25051 5개 영역의 표 매핑이 정확한가 (한국 SW 시험인증 실무 기준) | 25051 적용 정확성 |
| Q-MX-3 | 25059의 5개 신규 특성에 대한 시험소 해석 — *transparency·intervenability* 등 정의가 명확한가 | 25059 적용 가능성 |
| Q-MX-4 | 시험소가 *주로 다루는 25010 부특성*은 어떤 분포인가 (모든 부특성을 다 시험하나? 일부만?) | Phase 1 우선순위 재조정 가능 |
