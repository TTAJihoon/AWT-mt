"""대상 유형 어댑터 패키지 (D59~D63).

import 시 각 어댑터가 레지스트리에 자신을 등록한다. 무거운/선택적 의존
(playwright, uiautomation, pythonnet 등)은 각 어댑터가 scan/execute 시점에
lazy import 하므로, 패키지 import 자체는 가볍다.
"""
from __future__ import annotations

from app.adapters.registry import available_kinds, get_adapter, labels, register

# 어댑터 등록 (각 모듈이 register() 호출)
from app.adapters import web_adapter  # noqa: E402,F401  → "web" 등록

# 신규 대상 어댑터 — 구현되는 대로 활성화
try:
    from app.adapters import api_rest_adapter  # noqa: E402,F401  → "api_rest"
except Exception:
    pass
try:
    from app.adapters import api_code_adapter  # noqa: E402,F401  → "api_code"
except Exception:
    pass
try:
    from app.adapters import gui_adapter  # noqa: E402,F401  → "gui"
except Exception:
    pass

__all__ = ["get_adapter", "register", "available_kinds", "labels"]
