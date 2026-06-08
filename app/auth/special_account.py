"""특별 관리자 계정 — DB 연결 없이 로그인(방화벽/오프라인 대비 break-glass).

중앙 DB 접속이 방화벽 등으로 막혀도 관리자가 진입할 수 있도록 한 고정 계정.
요청에 따라 추가. 비밀번호는 평문 대신 SHA-256 해시로만 비교한다.
이 계정은 DB 유무와 무관하게 항상 admin 권한으로 로그인된다.
"""
from __future__ import annotations

import hashlib

SPECIAL_USERNAME = "jh91082"
# SHA-256("12sqec34!") — 평문을 소스에 두지 않기 위해 해시로 보관
_SPECIAL_PW_SHA256 = "61e310922cb252fb2856a3731d61017a118cdc97a15c9be2c07f8585d3a51b5f"
# DB 세션 토큰이 아닌, 오프라인 특별 로그인을 식별하는 토큰
SPECIAL_TOKEN = "SPECIAL-OFFLINE-ADMIN"
SPECIAL_ROLE = "admin"


def check(username: str, password: str) -> bool:
    """특별계정 자격 일치 여부 (DB 불필요)."""
    if username != SPECIAL_USERNAME:
        return False
    return hashlib.sha256((password or "").encode()).hexdigest() == _SPECIAL_PW_SHA256


def is_special_token(token: str | None) -> bool:
    return token == SPECIAL_TOKEN


def is_special_user(username: str | None) -> bool:
    return username == SPECIAL_USERNAME
