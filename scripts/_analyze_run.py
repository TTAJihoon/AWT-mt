"""임시 분석 스크립트: tc_verified.json INFERRED/Validation 분석."""
import json, sys
from pathlib import Path

run_id = sys.argv[1] if len(sys.argv) > 1 else "c2ffa6a5"
path = Path(f"data/runs/{run_id}/tc_verified.json")
data = json.loads(path.read_text(encoding="utf-8"))

inferred = [tc for tc in data if str(tc.get("source_quote", "")).startswith("INFERRED")]
manual   = [tc for tc in data if str(tc.get("source_quote", "")).startswith("MANUAL")]
invariant = [tc for tc in data if str(tc.get("source_quote", "")).startswith("INVARIANT")]

print(f"Total: {len(data)}  MANUAL: {len(manual)}  INVARIANT: {len(invariant)}  INFERRED: {len(inferred)}")
print()

# TC 구조 키
print("TC keys:", list(data[0].keys()))
print()

# INFERRED 샘플
print("=== INFERRED TC 샘플 ===")
for tc in inferred[:8]:
    sq = str(tc.get("source_quote", ""))[:100]
    print(f'  {tc["tc_id"]:20s} | {tc.get("requirement_id","?")} | {sq}')

print()

# validation 필드 확인
sample_keys = set()
for tc in data:
    for k in tc.keys():
        if "valid" in k.lower() or "v1" in k.lower() or "fail" in k.lower():
            sample_keys.add(k)
print("Validation-related keys:", sample_keys)
print()

# V3 관련 필드
for tc in data[:3]:
    for k in ["validation_results", "validations", "v3_result", "stage3"]:
        if k in tc:
            print(f"Field '{k}':", tc[k])
