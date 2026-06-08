"""그누보드5 웹 설치 자동화 (Playwright).

http://localhost:8080/install/ 3단계 마법사를 자동으로 완료한다.

사용:
    python scripts/install_gnuboard5.py [--admin-pw Gnuboard5!]
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",      default="http://localhost:8080")
    parser.add_argument("--admin-id", default="admin")
    parser.add_argument("--admin-pw", default="Gnuboard5!")
    parser.add_argument("--db-host",  default="db")
    parser.add_argument("--db-name",  default="gnuboard5")
    parser.add_argument("--db-user",  default="gnuboard")
    parser.add_argument("--db-pw",    default="gnuboard")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright 미설치. pip install playwright && playwright install chromium")
        sys.exit(1)

    base = args.url.rstrip("/")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def _fill(selector: str, value: str) -> bool:
            try:
                el = page.query_selector(selector)
                if el:
                    el.fill(value)
                    return True
            except Exception:
                pass
            return False

        # ── Step 1: 라이센스 동의 (index.php → install_config.php) ──────
        print("Step 1/3: 라이센스 동의...")
        page.goto(f"{base}/install/", wait_until="networkidle", timeout=20000)

        # agree 체크박스 체크 후 제출
        try:
            page.check("input[name=agree]", timeout=3000)
        except Exception:
            pass
        try:
            with page.expect_navigation(wait_until="networkidle", timeout=20000):
                page.click("input[type=submit]")
        except Exception:
            page.evaluate("document.querySelector('form').submit()")
            page.wait_for_load_state("networkidle", timeout=20000)

        print(f"  -> {page.url}")

        # ── Step 2: DB + 관리자 정보 입력 (install_config.php → install_db.php) ──
        print("Step 2/3: DB + 관리자 정보 입력...")

        # gnuboard5 필드명: mysql_host, mysql_user, mysql_pass, mysql_db
        _fill("#mysql_host", args.db_host)
        _fill("#mysql_user", args.db_user)
        _fill("#mysql_pass", args.db_pw)
        _fill("#mysql_db",   args.db_name)
        _fill("#admin_id",   args.admin_id)
        _fill("#admin_pass", args.admin_pw)

        # g5_install 체크박스 (재설치 허용)
        try:
            page.check("#g5_install", timeout=2000)
        except Exception:
            pass

        # 제출
        try:
            with page.expect_navigation(wait_until="networkidle", timeout=60000):
                page.click("input[type=submit]")
        except Exception:
            pass

        print(f"  -> {page.url}")
        body = page.inner_text("body") or ""
        for line in body.splitlines():
            if line.strip() and any(kw in line for kw in ["오류", "error", "실패", "완료", "성공"]):
                print(f"  {line.strip()[:100]}")

        # ── Step 3: 설치 완료 확인 ──────────────────────────────────────
        print("Step 3/3: 설치 완료 확인...")
        # install_db.php는 DB 생성 후 자동으로 완료 페이지로 이동하거나
        # 별도 submit이 필요할 수 있음
        for sel in ["input[type=submit]", "button[type=submit]"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    with page.expect_navigation(wait_until="networkidle", timeout=30000):
                        el.click()
                    break
            except Exception:
                pass

        print(f"  -> {page.url}")

        # 설치 성공 여부 확인
        body = page.inner_text("body") or ""
        if any(kw in body for kw in ["설치가 완료", "설치완료", "installation complete",
                                      "성공적으로", "완료되었습니다"]):
            print("\n설치 완료!")
        elif "이미 설치" in body or "already" in body.lower():
            print("\n이미 설치된 상태입니다.")
        else:
            print("\n[INFO] 설치 페이지 마지막 상태:")
            for line in body.splitlines()[:10]:
                if line.strip():
                    print(f"  {line.strip()[:80]}")

        # 메인 페이지 접근 확인
        page.goto(f"{base}/", wait_until="networkidle", timeout=15000)
        body2 = page.inner_text("body") or ""
        if "설치하기" not in body2 and "설치해주십시오" not in body2:
            print(f"\n[OK] 그누보드5 메인 페이지 정상 접근: {page.url}")
        else:
            print(f"\n[WARN] 아직 설치가 필요한 상태: {page.url}")

        browser.close()


if __name__ == "__main__":
    main()
