"""Python 러너 (D62) — importlib + inspect로 모듈 함수를 in-process 호출."""
from __future__ import annotations

import importlib
import importlib.util
import inspect
from pathlib import Path
from typing import Any

from app.adapters.api_code.base_runner import Symbol


def _load_module(target_config: dict):
    mp = target_config.get("module_path") or target_config.get("module")
    if not mp:
        raise ValueError("api_code(python): target_config에 module_path 또는 module 필요")
    if str(mp).endswith(".py") or "/" in str(mp) or "\\" in str(mp):
        spec = importlib.util.spec_from_file_location("awt_target_mod", mp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    return importlib.import_module(mp)


def _ann_name(annotation) -> str:
    if annotation is inspect.Signature.empty:
        return ""
    return getattr(annotation, "__name__", str(annotation))


class PythonRunner:
    lang = "python"

    def list_symbols(self, target_config: dict) -> list[Symbol]:
        mod = _load_module(target_config)
        symbols: list[Symbol] = []
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            if name.startswith("_"):
                continue
            if getattr(fn, "__module__", None) != mod.__name__:
                continue  # 이 모듈에서 정의된 함수만(임포트된 것 제외)
            sig = inspect.signature(fn)
            params = []
            for pn, p in sig.parameters.items():
                if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
                    continue
                required = (p.default is p.empty)
                params.append({
                    "name": pn,
                    "annotation": _ann_name(p.annotation),
                    "required": required,
                    "default": None if p.default is p.empty else repr(p.default),
                    "kind": str(p.kind),
                })
            symbols.append(Symbol(
                symbol=name, name=name, qualname=name,
                signature=str(sig), doc=(inspect.getdoc(fn) or ""),
                params=params, returns=_ann_name(sig.return_annotation),
            ))
        return symbols

    def invoke(self, sym: Symbol, args: list, kwargs: dict,
               target_config: dict) -> dict:
        mod = _load_module(target_config)
        fn = getattr(mod, sym.name)
        try:
            rv = fn(*(args or []), **(kwargs or {}))
            return {"ok": True, "return": repr(rv)[:300], "exception": None, "message": ""}
        except Exception as e:  # noqa: BLE001 — 대상 라이브러리의 모든 예외 포착
            return {"ok": False, "return": "", "exception": type(e).__name__,
                    "message": str(e)[:200]}
