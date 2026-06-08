"""C/네이티브 DLL 러너 (D62) — ctypes 호출.

C는 리플렉션이 불가하므로 사용자가 함수 시그니처를 명세로 제공한다.
target_config:
  dll_path: "C:/path/lib.dll"
  signatures: [{"name":"add","restype":"int","argtypes":["int","int"]}, ...]
  또는 signatures_path: 위 리스트가 담긴 JSON 파일 경로
"""
from __future__ import annotations

import ctypes
import json
from pathlib import Path

from app.adapters.api_code.base_runner import Symbol

# C 타입명 → ctypes 타입
_CTYPES = {
    "void": None, "int": ctypes.c_int, "int32": ctypes.c_int, "long": ctypes.c_long,
    "int64": ctypes.c_longlong, "uint": ctypes.c_uint, "short": ctypes.c_short,
    "float": ctypes.c_float, "double": ctypes.c_double,
    "char*": ctypes.c_char_p, "const char*": ctypes.c_char_p, "string": ctypes.c_char_p,
    "bool": ctypes.c_bool, "size_t": ctypes.c_size_t, "void*": ctypes.c_void_p,
}


def _load_signatures(tc: dict) -> list[dict]:
    if tc.get("signatures"):
        return list(tc["signatures"])
    sp = tc.get("signatures_path")
    if sp:
        return json.loads(Path(sp).read_text(encoding="utf-8"))
    raise ValueError("api_code(c): target_config에 signatures 또는 signatures_path 필요")


class CRunner:
    lang = "c"

    def list_symbols(self, target_config: dict) -> list[Symbol]:
        sigs = _load_signatures(target_config)
        symbols: list[Symbol] = []
        for s in sigs:
            argtypes = s.get("argtypes", []) or []
            params = [{
                "name": f"arg{i}",
                "annotation": at,
                "required": True,
                "default": None,
                "kind": "POSITIONAL_ONLY",
            } for i, at in enumerate(argtypes)]
            sig = f"({', '.join(argtypes)}) -> {s.get('restype','void')}"
            symbols.append(Symbol(
                symbol=s["name"], name=s["name"], qualname=s["name"],
                signature=sig, doc=s.get("doc", ""), params=params,
                returns=s.get("restype", "void"),
            ))
        return symbols

    def invoke(self, sym: Symbol, args: list, kwargs: dict, target_config: dict) -> dict:
        dll_path = target_config.get("dll_path") or target_config.get("module_path")
        if not dll_path:
            return {"ok": False, "return": "", "exception": "ConfigError",
                    "message": "dll_path 미지정"}
        # kwargs(arg0,arg1,...)를 순서대로 위치 인자로
        ordered = [kwargs[p["name"]] for p in sym.params if p["name"] in kwargs] if kwargs else list(args or [])
        try:
            lib = ctypes.CDLL(str(dll_path))
            fn = getattr(lib, sym.name)
            fn.restype = _CTYPES.get((sym.returns or "void").lower(), ctypes.c_int)
            fn.argtypes = [_CTYPES.get((p["annotation"] or "int").lower(), ctypes.c_int)
                           for p in sym.params]
            conv = []
            for p, v in zip(sym.params, ordered):
                if _CTYPES.get((p["annotation"] or "").lower()) is ctypes.c_char_p and isinstance(v, str):
                    v = v.encode("utf-8")
                conv.append(v)
            rv = fn(*conv)
            if isinstance(rv, bytes):
                rv = rv.decode("utf-8", "replace")
            return {"ok": True, "return": repr(rv)[:300], "exception": None, "message": ""}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "return": "", "exception": type(e).__name__,
                    "message": str(e)[:200]}
