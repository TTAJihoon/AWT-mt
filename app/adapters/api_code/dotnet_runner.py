"""C#/.NET 러너 (D62) — pythonnet(clr)로 어셈블리 리플렉션 + 호출.

target_config:
  dll_path: ".../MyLib.dll"
  types: ["MyLib.Calculator", ...]  (선택 — 미지정 시 어셈블리의 public 타입 전체)
의존: pip install pythonnet  (미설치 시 명확한 안내)
"""
from __future__ import annotations

from pathlib import Path

from app.adapters.api_code.base_runner import Symbol


def _require_clr():
    try:
        import clr  # noqa: F401
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            "api_code(dotnet): pythonnet 미설치. `pip install pythonnet` 후 재시도."
        ) from e
    import clr
    return clr


class DotNetRunner:
    lang = "dotnet"

    def _load_assembly(self, tc: dict):
        clr = _require_clr()
        import System
        dll = tc.get("dll_path") or tc.get("module_path")
        if not dll:
            raise ValueError("api_code(dotnet): dll_path 필요")
        return System.Reflection.Assembly.LoadFile(str(Path(dll).resolve()))

    def list_symbols(self, target_config: dict) -> list[Symbol]:
        asm = self._load_assembly(target_config)
        want = set(target_config.get("types") or [])
        symbols: list[Symbol] = []
        for t in asm.GetTypes():
            if not t.IsPublic:
                continue
            if want and t.FullName not in want:
                continue
            for m in t.GetMethods():
                if not m.IsPublic or m.IsSpecialName:
                    continue
                ps = m.GetParameters()
                params = [{
                    "name": p.Name,
                    "annotation": p.ParameterType.Name,
                    "required": True,
                    "default": None,
                    "kind": "POSITIONAL_OR_KEYWORD",
                } for p in ps]
                key = f"{t.Name}.{m.Name}"
                symbols.append(Symbol(
                    symbol=key, name=m.Name, qualname=key,
                    signature=f"({', '.join(p.ParameterType.Name for p in ps)}) -> {m.ReturnType.Name}",
                    doc="", params=params, returns=m.ReturnType.Name,
                    raises=[],
                ))
        return symbols

    def invoke(self, sym: Symbol, args: list, kwargs: dict, target_config: dict) -> dict:
        try:
            asm = self._load_assembly(target_config)
            type_name = sym.qualname.rsplit(".", 1)[0]
            target_type = next(t for t in asm.GetTypes() if t.Name == type_name)
            ordered = [kwargs[p["name"]] for p in sym.params if p["name"] in kwargs] \
                if kwargs else list(args or [])
            import System
            # static 우선; 인스턴스 메서드면 기본 생성자로 인스턴스 생성
            method = target_type.GetMethod(sym.name)
            instance = None
            if not method.IsStatic:
                instance = System.Activator.CreateInstance(target_type)
            rv = method.Invoke(instance, list(ordered))
            return {"ok": True, "return": repr(rv)[:300], "exception": None, "message": ""}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "return": "", "exception": type(e).__name__,
                    "message": str(e)[:200]}
