"""LLM Call Contract 로더 (prompts/*.md 파일 파싱)."""
from __future__ import annotations
import re
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


class Contract:
    def __init__(self, contract_id: str, version: str, model: str,
                 max_input_tokens: int, max_output_tokens: int,
                 system_prompt: str, user_template: str):
        self.contract_id = contract_id
        self.version = version
        self.model = model
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.system_prompt = system_prompt
        self.user_template = user_template

    def render_user(self, **kwargs) -> str:
        text = self.user_template
        for k, v in kwargs.items():
            text = text.replace("{" + k + "}", str(v))
        return text


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not m:
        return {}, content
    fm_text, body = m.group(1), m.group(2)
    fm = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, body


def load(contract_id: str) -> Contract:
    path = _PROMPTS_DIR / f"{contract_id.lower().replace('_', '_')}.md"
    # DOM_SPEC → dom_spec.md
    name_map = {
        "DOM_SPEC":        "dom_spec",
        "TC_DESIGN":       "tc_design",
        "TC_DESIGN_GROUP": "tc_design_group",
        "TC_FLOW":         "tc_flow",
        "TC_V10_GROUP":    "tc_v10_group",
        "TC_REGEN":        "tc_regen",
        "FAILURE_ANALYSIS":"failure_analysis",
        "PATTERN_EXTRACT": "pattern_extract",
        "FEATURE_CONSOLIDATE": "feature_consolidate",
    }
    fname = name_map.get(contract_id, contract_id.lower())
    path = _PROMPTS_DIR / f"{fname}.md"
    content = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(content)

    # body → [System] / [User] 분리
    sys_m = re.search(r"\[System\](.*?)(?=\[User\])", body, re.DOTALL)
    usr_m = re.search(r"\[User\](.*)", body, re.DOTALL)
    system_prompt = sys_m.group(1).strip() if sys_m else ""
    user_template = usr_m.group(1).strip() if usr_m else ""

    return Contract(
        contract_id=fm.get("contract_id", contract_id),
        version=fm.get("version", "v1.0"),
        model=fm.get("model", "claude-sonnet-4-6"),
        max_input_tokens=int(fm.get("max_input_tokens", 4000)),
        max_output_tokens=int(fm.get("max_output_tokens", 2000)),
        system_prompt=system_prompt,
        user_template=user_template,
    )
