"""Java 러너 (D62) — jpype로 JVM 기동 + 클래스 리플렉션 + 호출.

target_config:
  classpath: ".../mylib.jar"  (또는 [".../a.jar", ".../classes"])
  classes: ["com.example.Calculator", ...]  (필수 — jar 전체 스캔은 비용 큼)
의존: pip install JPype1  (미설치 시 명확한 안내)
"""
from __future__ import annotations

from app.adapters.api_code.base_runner import Symbol


def _require_jpype():
    try:
        import jpype  # noqa: F401
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            "api_code(java): JPype1 미설치. `pip install JPype1` 후 재시도."
        ) from e
    import jpype
    return jpype


def _ensure_jvm(tc: dict):
    jpype = _require_jpype()
    cp = tc.get("classpath")
    cps = cp if isinstance(cp, list) else [cp] if cp else []
    if not jpype.isJVMStarted():
        jpype.startJVM(classpath=cps)
    return jpype


class JavaRunner:
    lang = "java"

    def list_symbols(self, target_config: dict) -> list[Symbol]:
        jpype = _ensure_jvm(target_config)
        from java.lang import Class  # type: ignore
        classes = target_config.get("classes") or []
        if not classes:
            raise ValueError("api_code(java): target_config['classes'] 필요(클래스 FQN 목록)")
        symbols: list[Symbol] = []
        for fqn in classes:
            cls = Class.forName(fqn)
            simple = fqn.rsplit(".", 1)[-1]
            for m in cls.getMethods():
                if m.getDeclaringClass().getName() == "java.lang.Object":
                    continue
                ptypes = [p.getSimpleName() for p in m.getParameterTypes()]
                params = [{
                    "name": f"arg{i}", "annotation": pt, "required": True,
                    "default": None, "kind": "POSITIONAL_ONLY",
                } for i, pt in enumerate(ptypes)]
                key = f"{simple}.{m.getName()}"
                symbols.append(Symbol(
                    symbol=key, name=m.getName(), qualname=f"{fqn}.{m.getName()}",
                    signature=f"({', '.join(ptypes)}) -> {m.getReturnType().getSimpleName()}",
                    doc="", params=params, returns=m.getReturnType().getSimpleName(),
                ))
        return symbols

    def invoke(self, sym: Symbol, args: list, kwargs: dict, target_config: dict) -> dict:
        try:
            jpype = _ensure_jvm(target_config)
            fqn = sym.qualname.rsplit(".", 1)[0]
            cls = jpype.JClass(fqn)
            ordered = [kwargs[p["name"]] for p in sym.params if p["name"] in kwargs] \
                if kwargs else list(args or [])
            # static 우선 시도 → 실패 시 인스턴스 생성
            try:
                rv = getattr(cls, sym.name)(*ordered)
            except TypeError:
                rv = getattr(cls(), sym.name)(*ordered)
            return {"ok": True, "return": repr(rv)[:300], "exception": None, "message": ""}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "return": "", "exception": type(e).__name__,
                    "message": str(e)[:200]}
