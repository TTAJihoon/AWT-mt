# 메트릭 Operational Definitions

**상태:** **양식 골격.** 시험소가 보유한 ISO/IEC 25023:2016, 25051:2014, (조건부) 25059:2023 원본을 기반으로 시험원이 채워 확정.

> **본 문서의 목적:** 각 메트릭의 *시험소 내부 공식 정의*를 한 곳에 모아 AWT·시험원 양쪽이 동일 정의를 참조. AWT의 학습 데이터 기반 정의와 시험소 원본 정의가 다를 수 있어, 본 문서가 *최종 권위*가 된다.

---

## 1. 작성 원칙

- 메트릭마다 *입력·계산식·출력·임계·해석*을 1페이지 이내로 정리
- 25023 원본 표기(메트릭 ID·이름)를 정확히 사용
- AWT가 자동 계산하는 경우 *계산식이 AWT 구현과 일치*해야 함
- 임계는 시험소 정책 또는 25023 권고

---

## 2. 메트릭 정의 양식

```
[메트릭 ID]: 25023의 공식 ID
[메트릭 이름]: 한국어 + 영어
[해당 25010 부특성]:
[Layer 분류]: L1 / L2 / L3
[목적]: 무엇을 측정하는가
[입력 X]: 측정에 필요한 데이터
[계산식 F(X)]: 정량 공식
[출력 단위]: %, 시간, 비율 등
[임계]: 권고값 (예: ≥ 90%)
[해석]: 결과 의미·후속 행동
[AWT 구현 참조]: 구현 시점에 채움 (Phase 2)
[비고]: 25023과 시험소 정책 차이가 있다면 명시
```

---

## 3. 채울 메트릭 목록 (Layer 1 우선)

> 이 목록은 `01-characteristics-matrix.md` §2에서 L1으로 분류된 메트릭 우선.

### 3.1. Functional Suitability

- [ ] **FCp-1-G** (?) Functional completeness — 기능 완전성
- [ ] **FCo-1-G** (?) Functional correctness — 기능 정확성
- [ ] **FAp-1-G** (?) Functional appropriateness — 기능 적절성 (L2)

### 3.2. Performance Efficiency

- [ ] Time behavior — 응답시간 평균/p95/p99
- [ ] Resource utilization — 자원 사용량 (L2)
- [ ] Capacity — 용량 (L3)

### 3.3. Compatibility

- [ ] Browser compatibility — 브라우저별 PASS 비율
- [ ] Interoperability — 외부 시스템 연동 (L2)

### 3.4. Reliability

- [ ] Maturity — 결함 밀도 (defect density)
- [ ] Availability — 가동률 (L2)
- [ ] Fault tolerance — 결함 허용성 (L2)
- [ ] Recoverability — 복구성 (L2)

### 3.5. Usability (L2/L3 위주)

- [ ] Appropriateness recognizability (L3)
- [ ] Learnability (L3)
- [ ] Operability (L2)
- [ ] User error protection (L2)
- [ ] Accessibility (L2 자동 부분, L3 심층 부분)

### 3.6. ISO/IEC 25051 — RUSP

- [ ] 제품 설명서 완전성
- [ ] 사용자 문서 완전성
- [ ] 시험 문서 자체 품질 (AWT 자기 점검)

### 3.7. ISO/IEC 25059 (AI 제품 조건부, D15)

- [ ] Functional adaptability
- [ ] User controllability
- [ ] Transparency
- [ ] Robustness
- [ ] Intervenability

---

## 4. 임계 정책

각 메트릭의 *합격 임계*는 다음 중 하나로 결정:
1. **25023 원본 권고치** 그대로
2. **시험소 내부 정책** (특정 제품군별 차등 가능)
3. **고객사 협의** (인증 받으려는 SW의 특성)

본 문서의 [임계] 항목에는 *어떤 출처로 정한 임계인지* 명시 권장 (예: "25023 권고", "시험소 표준 v3.2", "고객사 협의 PRD-2026-12").

---

## 5. AWT의 자동 계산 vs 수동 측정 구분

| 메트릭 | AWT 자동 | 수동 |
|---|---|---|
| FC (Functional Completeness) | ✓ | — |
| FCo (Functional Correctness) | ✓ | — |
| Time behavior | ✓ | — |
| Defect density | ✓ | — |
| Browser compatibility | ✓ | — |
| (25051) 시험 문서 자체 | ✓ (자기 점검) | — |
| Functional appropriateness | — | ✓ (시험원) |
| User error protection | 부분 | ✓ (시험원 4축) |
| Accessibility | 부분 (axe) | ✓ (스크린리더) |
| Usability 인지·학습 | — | ✓ (SUS 등) |
| Capacity | — | ✓ (부하시험 도구) |
| Security 심층 | — | ✓ (보안 전문가) |
| 25059 AI 5종 | 부분 | ✓ |

---

## 6. 본 문서의 다음 작업

본 문서는 *목록·양식*만 제공. 실제 채움 작업은 시험원·관리자가 수행:

1. 시험소 보유 25023:2016 원본에서 메트릭 ID 정확히 추출
2. 위 §2 양식에 따라 1메트릭씩 채움
3. AWT 자동 계산 메트릭은 *공식·예시 데이터*까지 명시
4. 임계 정책 §4 결정
5. Phase 2 진입 시 AWT 구현 참조 코드 링크 추가

---

## 7. AWT가 *현재 알고 있는* 학습 데이터 기반 정의 (참고)

> **주의:** 아래는 *시험소 원본이 확정되기 전까지의 잠정* 참조. 25023 원본과 차이 가능성 있음. 최종 정의는 §2 양식 채움 결과로 대체.

### 7.1. Functional Completeness (잠정)
```
FC = 1 - (구현되지 않은 기능 수) / (명세된 기능 총 수)
```
또는 시험된 기능 기준:
```
FC = (TC가 존재하는 명세 기능 수) / (명세된 기능 총 수)
```

### 7.2. Functional Correctness (잠정)
```
FCo = (정확히 동작한 TC 수) / (실행된 TC 총 수)
```

### 7.3. Defect Density (잠정)
```
DD = (발견 결함 수) / (시험 수행 기능 수)  또는
DD = (FAIL TC 수) / (TC 총 수)
```

### 7.4. Time Behavior (잠정)
```
응답시간 평균·p50·p95·p99 (ms)
대상: 단위 액션 timing
```

위 정의는 *AWT의 자동 계산 구현 시 참조*되나, 시험소 원본이 다르면 §2 양식 결과를 우선.
