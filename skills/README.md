# skills/ — 배포 가능한 Claude Sub-Skill 패키지

> **상태:** 비어 있음 — 구현 단계에서 채움

이 폴더는 AWT 프로젝트가 만들어내는, **외부에 분리 배포 가능한 Claude Skill 패키지**의 실제 구현체를 담는다.

각 sub-skill은 `skills/<skill-name>/SKILL.md` 형태로 자기 완결적으로 패키징되어, 다른 프로젝트나 외부 사용자가 단독 설치 가능해야 한다.

## 예정된 sub-skill (`doc/05-deployable-skills/candidates.md` 참조)

- `web-dom-scanner/`
- `manual-to-feature-list/`
- `tc-traceability-validator/`
- `anonymizer-for-defects/`
- `axe-accessibility-runner/`
- `mutation-score-runner/`

위 후보들은 모두 *설계 검토 완료 + 구현 결정 단계*를 거친 뒤에만 실제 패키지로 만들어진다 (개발 지침 1).

## AWT 본체 skill과의 관계

- **AWT 본체** = 프로젝트 루트 `SKILL.md` — 시험소 내부에서 end-to-end 호출.
- **Sub-skill** = `skills/<name>/SKILL.md` — 각각 독립 호출, AWT 본체도 내부적으로 호출 가능.
