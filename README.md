# AWT — AI-driven Web Testing for SW Certification

ISO/IEC 25023:2016 + 25051:2014 + (조건부) 25059:2023 기반 웹 SW 시험인증 자동화. 매뉴얼·기능리스트·URL·결함샘플 → TC 설계·검토·자동 실행·판정 → 시험소 표준 산출물.

**프로덕션:** Windows 데스크탑 앱 (.exe) — Python + Anthropic API + 로컬 Playwright + DB 인증
**PoC 환경:** Claude Code (prompt 품질 검증용, 현재 단계)

---

## 처음 사용한다면

→ **[MANUAL.md](MANUAL.md)** — 설치 / Provider 선택 / 5가지 실행 시나리오 / 결과 해석 / 트러블슈팅. **이 한 문서로 시작 가능**.

## 다른 PC에서 이어서 작업하려면

```bash
git clone <repo-url> AWT
cd AWT
```

→ **[CONTINUE.md](CONTINUE.md)** 를 먼저 읽어. 현재 작업 상태·다음 행동·읽어야 할 문서 순서가 정리되어 있어.

---

## 폴더 구조

| 폴더/파일 | 용도 |
|---|---|
| `doc/` | **설계 문서 (모든 결정의 단일 출처)** — 7개 파일 + archive |
| `data/poc/` | PoC 진행 산출물 (α 완료, β 대기) |
| `tools/` | 개발용 스크립트 (Excel 빌더 등) |
| `prompts/` | LLM Call Contract 프롬프트 (Phase 1 개발 시 작성) |
| `app/` | 데스크탑 앱 소스 (Phase 1 개발 시 생성) |
| `skills/` | 분리 배포 가능 sub-skill (현재 미사용) |
| `SKILL.md` | Claude Code skill 정의 (PoC 환경용) |
| `CONTINUE.md` | 이어서 작업할 때 진입점 |

---

## 현재 진행 상황

- ✅ **설계 완료** — `doc/` 7개 문서 (아키텍처·LLM·TC·ISO·PoC·결정)
- ✅ **PoC-α 완료** — TC 생성 41개, V1·V4·V5 PASS / V2·V3 부분 PASS
- ⏳ **PoC-β 대기** — 사용자 reviewer 검토 중 (`data/poc/2026-05-19/output/tc_review.xlsx`)
- ⏸ **PoC-γ 예정** — β 통과 후 자동 실행 시뮬레이션
- ⏸ **Phase 1 (Desktop App)** — PoC γ 통과 후 개발 진입

---

## 개발 지침 (불변)

1. **설계 우선** — 구현 전 `doc/`에서 합의·동결
2. **수정계획 제시** — 즉시 코딩 금지, 변경안 사전 제시
3. **추측 금지** — 모르면 묻기
4. **Skill화 고려** — 분리 배포 가능한 단위로 설계 (Phase 2)
5. **디렉터리 확인** — 새 파일 작성 전 위치 확인

→ 자세한 설계 진입은 [doc/README.md](doc/README.md) 참조.
