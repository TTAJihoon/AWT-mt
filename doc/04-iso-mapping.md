# ISO/IEC 25023 × Layer 자동화 매트릭스

> ISO/IEC 25010(품질 모델) + 25023(품질 측정 메트릭) + 25051(COTS 요구) 기준으로 AWT가 자동화 가능한 영역과 시험원이 책임지는 영역을 분류한다.
> 25059(AI 시스템 품질)는 AI 제품에만 조건부 적용 (D15).

---

## 1. Layer 분류

| Layer | 의미 | 책임 | TC 처리 |
|---|---|---|---|
| **L1** | AWT 자동 (생성+실행+판정) | AWT | confidence 기반 자동 승인 후 Gate 빠른 확인 |
| **L2** | AWT 보조 + 시험원 검토 | AWT + 시험원 | Gate에서 시험원 검토 필수 |
| **L3** | 시험원 전담 | 시험원 | AWT는 유관 정보만 정리, 평가는 사람 |

**판정 기준 (4조건 모두 충족 → L1):**
1. 메트릭이 객관적 기준으로 측정 가능 (인간 인지 불요)
2. Oracle을 명세에서 도출 가능
3. False PASS/FAIL 위험이 confidence로 정량화 가능
4. 재현성·추적성 강제 가능

---

## 2. ISO/IEC 25010 × 25023 매트릭스

### 2.1 Functional Suitability (기능적 적합성)

| 부특성 | 자동 | Layer | 비고 |
|---|---|---|---|
| Functional completeness | ✓ | **L1** | 기능리스트 vs TC 매핑 직접 계산 |
| Functional correctness | ✓ | **L1** | TC 실행 PASS 비율 |
| Functional appropriateness | ◐ | **L2** | 적절성 판단에 도메인 지식 |

### 2.2 Performance Efficiency (성능 효율성)

| 부특성 | 자동 | Layer | 비고 |
|---|---|---|---|
| Time behavior | ✓ | **L1** | Playwright 타이밍 측정 |
| Resource utilization | ◐ | **L2** | 브라우저 측만, 서버는 외부 모니터링 |
| Capacity | ✗ | **L3** | 부하시험 도구 별도 (Phase 2+) |

### 2.3 Compatibility (호환성)

| 부특성 | 자동 | Layer | 비고 |
|---|---|---|---|
| Co-existence | ✗ | **L3** | 환경 셋업 필요 |
| Interoperability | ◐ | **L2** | API mock 일부 자동 |
| 브라우저 호환성 | ✓ | **L1** | Playwright multi-browser |

### 2.4 Usability (사용성) — 자동화 한계 영역

| 부특성 | 자동 | Layer | 비고 |
|---|---|---|---|
| Appropriateness recognizability | ✗ | **L3** | 인간 인지 필수 |
| Learnability | ✗ | **L3** | SUS·USE 설문 |
| Operability | ◐ | **L2** | 탭 순서·키보드 일부 자동 |
| User error protection | ◐ | **L2** | negative_basic은 L1, 메시지 적절성은 L2 |
| UI aesthetics | ✗ | **L3** | 디자인 vs 버그 구분 불가 |
| Accessibility | ◐ | **L2** | axe-core 30~40% 검출 |

### 2.5 Reliability (신뢰성)

| 부특성 | 자동 | Layer | 비고 |
|---|---|---|---|
| Maturity | ✓ | **L1** | 결함 밀도 = FAIL 수 / 총 수 |
| Availability | ◐ | **L2** | 단시간만 자동, SLA는 장기 |
| Fault tolerance | ◐ | **L2** | negative_deep 일부 |
| Recoverability | ◐ | **L2** | 시나리오는 자동, 완전성 판단은 사람 |

### 2.6 Security (보안)

| 부특성 | 자동 | Layer | 비고 |
|---|---|---|---|
| Confidentiality | ◐ | **L2** | IDOR 기초 자동 |
| Integrity | ◐ | **L2** | 동일 |
| Non-repudiation | ✗ | **L3** | 로그 정책 평가 |
| Accountability | ✗ | **L3** | 감사 로그 검토 |
| Authenticity | ◐ | **L2** | 로그인 L1, 정책 L3 |

> 보안 심층은 OWASP·ISO 27001 별도 표준 영역.

### 2.7 Maintainability (유지보수성)

| 부특성 | 자동 | Layer | 비고 |
|---|---|---|---|
| Modularity/Reusability/Analyzability/Modifiability | ✗ | **L3 또는 N/A** | 웹 시험은 보통 블랙박스 |
| Testability | ◐ | **L2** | AWT 자체 메트릭 |

### 2.8 Portability (이식성)

| 부특성 | 자동 | Layer | 비고 |
|---|---|---|---|
| Adaptability | ◐ | **L2** | 브라우저별은 L1 |
| Installability | ✗ | **L3** | 웹은 보통 N/A |
| Replaceability | ✗ | **L3** | 평가 도메인 |

---

## 3. ISO/IEC 25051 (COTS) 추가 요구

| 영역 | 요구 | 자동 | Layer |
|---|---|---|---|
| 제품 설명서 | 제품명·버전·기능·요구환경 | ◐ | **L2** |
| 사용자 문서 | 설치·운영·문제해결 | ◐ | **L2** |
| 제품 품질 | 25010 기반 | ↑§2 | ↑§2 |
| 사용 시 품질 | 실사용 효과·만족도 | ✗ | **L3** |
| 시험 문서 | 시험 절차·결과 기록 | ✓ | **L1** — AWT 산출물 자체 |

> 한국 SW 시험인증에서 25051 적용 비중 큼. 제품 설명서·사용자 문서 정합성 검토가 L2의 핵심 작업.

---

## 4. ISO/IEC 25059 (AI 시스템) — 조건부 적용 (D15)

**적용 조건:** AI를 *주된 기능*으로 포함한 제품일 때만.

### 4.1 기존 특성의 AI 맥락 재정의

| 부특성 | AI 맥락 변화 | AWT 대응 | Layer |
|---|---|---|---|
| Functional correctness | 비결정적 출력 → 분포 평가 | TC 반복 + 통계 판정 (Phase 3) | L2 → L1 |
| Reliability/Maturity | 재학습 시 성능 변화 | 모델 버전 메타데이터 강제 | L2 |

### 4.2 AI 특화 신규 특성

| 부특성 | 의미 | 자동 | Layer |
|---|---|---|---|
| Functional adaptability | 새 입력·맥락 적응 | ◐ | L2 (metamorphic 시험) |
| User controllability | 사용자 개입·조정 | ◐ | L2 |
| Transparency | AI 결정 근거 공개 | ◐ | L2 |
| Robustness | adversarial 입력 견고성 | ◐ | L2 |
| Intervenability | 동작 중단·우회 | ◐ | L2 |

### 4.3 TC 스키마 영향

25059 적용 시 옵션 컬럼 추가:
- `ai_repetition_count`, `ai_pass_rate`, `ai_model_version`, `ai_input_variation`

---

## 5. Layer별 통합 요약

**L1 (AWT 자동) — 1차 전수 시험의 핵심:**
Functional Suitability 전부 + Time behavior + 브라우저 호환성 + Maturity + 25051 시험 문서 자체 산출

→ 시험소 처리량 증가의 70~80% 추정

**L2 (AWT 보조 + 시험원 검토) — 시험원의 핵심 작업:**
Functional appropriateness + Operability/User error protection/Accessibility 일부 + Resource/Fault tolerance/Recoverability + Security 기초 + 25051 문서 정합성 + 25059 5종 거의 전부

→ AWT는 *검토 시간 단축 도구*

**L3 (시험원 전담) — 정의상 자동화 불가:**
Usability Recognizability/Learnability/Aesthetics + Capacity + Security 심층 + Maintainability 소스 메트릭 + Portability Replaceability

→ AWT는 *유관 정보 정리만*

---

## 6. AWT가 측정 가능한데 현재 시험소가 측정 안 하는 것 (D21)

| 메트릭 | 자동 가능 | 도입 Phase |
|---|---|---|
| Functional completeness % | ✓ | Phase 2 |
| Functional correctness % | ✓ | Phase 2 |
| Time behavior 분포 | ✓ | Phase 2 |
| Maturity (defect density) | ✓ | Phase 2 |

→ Phase 2의 핵심 가치: 시험소가 측정 안 하는 메트릭 %를 자동 산출해 *내부 KPI*로 제공. 외부 보고서 포함 여부는 별도 결정.

---

## 7. 미해결 (운영 검수 후 확정)

| ID | 항목 |
|---|---|
| Q-MX-1 | §2 매트릭스 분류가 시험소 실무와 일치하는가 |
| Q-MX-2 | 25051 5개 영역 매핑 정확성 (한국 시험인증 실무 기준) |
| Q-MX-3 | 25059 5개 신규 특성에 대한 시험소 해석 |
| Q-MX-4 | 시험소가 주로 다루는 25010 부특성 분포 |
