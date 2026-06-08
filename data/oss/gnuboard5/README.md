# 그누보드5 — AWT Phase 2 시험 대상 (D47)

## 환경 구성

### 1. 그누보드5 소스 다운로드

```bash
# app/ 디렉터리에 그누보드5 소스 배치
git clone https://github.com/gnuboard/gnuboard5.git app
```

### 2. Docker 실행

```bash
cd data/oss/gnuboard5
docker compose up -d

# 로그 확인
docker compose logs -f web
```

접속: http://localhost:8080

### 3. 그누보드5 초기 설치

브라우저에서 http://localhost:8080/install 접속 후:

| 항목 | 값 |
|---|---|
| DB 서버 | `db` |
| DB 포트 | `3306` |
| DB 이름 | `gnuboard5` |
| DB 사용자 | `gnuboard` |
| DB 비밀번호 | `gnuboard` |
| 관리자 ID | `admin` |
| 관리자 비밀번호 | (임의 설정) |

### 4. AWT 실행 설정 예시

```python
from app.core.orchestrator import RunConfig

config = RunConfig(
    api_key="sk-ant-...",
    target_url="http://localhost:8080",
    input_files=["data/oss/gnuboard5/manual/gnuboard5_spec.md"],
    auth_sequence=[
        {"action": "goto", "url": "http://localhost:8080/bbs/login.php"},
        {"action": "fill", "selector": "#mb_id", "value": "admin"},
        {"action": "fill", "selector": "#mb_password", "value": "admin비밀번호"},
        {"action": "click", "selector": ".btn_submit"},
    ],
)
```

## 파일 구조

```
data/oss/gnuboard5/
├── docker-compose.yml    # Docker Compose 설정
├── php.ini               # PHP 설정
├── app/                  # 그누보드5 소스 (git clone 필요)
└── manual/
    └── gnuboard5_spec.md # 기능 명세서 (Stage 1 입력)
```

## 주요 테스트 시나리오 (예상 leaf)

| 대분류 | 중분류 | leaf |
|---|---|---|
| 회원 | 회원가입 | 정상 가입, 중복 아이디, 비밀번호 미달, 약관 미동의 |
| 회원 | 로그인 | 정상 로그인, 틀린 비밀번호, 비로그인 접근 |
| 게시판 | 글 작성 | 정상 작성, 제목 누락, 첨부파일 제한 초과 |
| 게시판 | 글 조회 | 목록, 상세, 비밀글 권한 |
| 게시판 | 댓글 | 작성, 수정, 삭제, 대댓글 |
| 검색 | 통합검색 | 제목 검색, 내용 검색, 결과 없음 |
| 포인트 | 적립/차감 | 게시글 작성 시 적립, 다운로드 시 차감 |
| 관리자 | 게시판 | 게시판 생성, 공지글 설정, 강제 삭제 |
