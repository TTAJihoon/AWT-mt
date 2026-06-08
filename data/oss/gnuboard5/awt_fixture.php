<?php
/**
 * AWT 테스트 픽스처 헬퍼 — gnuboard5 내부 함수로 테스트 계정·게시글 직접 생성.
 *
 * ⚠️ 보안 경고: 이 파일은 인증 없이 회원/게시글을 생성합니다.
 *    AWT 자동화 테스트 전용 (로컬 Docker)입니다. 프로덕션 배포 절대 금지.
 *    docker-compose.yml 에서 ./awt_fixture.php:/app/awt_fixture.php:ro 로 마운트됨.
 *
 * gnuboard5 공개 회원가입은 CAPTCHA로 막혀 있어 Playwright 자동화가 불가능하므로,
 * 이 헬퍼가 common.php 를 include 하여 gnuboard5 내부 DB 함수로 직접 삽입한다.
 *
 * API (모두 JSON 응답):
 *   ?action=check_member&mb_id=awt01
 *       → {"status":"exists"} | {"status":"none"}
 *   ?action=create_member&mb_id=awt01&mb_pw=Awt1234!
 *       → {"status":"created","mb_id":"awt01"} | {"status":"exists"} | {"status":"error","msg":...}
 *   ?action=setup_board&bo_table=free
 *       → {"action":"setup_board","status":"ok"}
 *   ?action=find_post&bo_table=free&mb_id=awt01
 *       → {"status":"found","wr_id":N} | {"status":"none"}
 *   ?action=create_post&bo_table=free&mb_id=awt01&subject=...&content=...
 *       → {"status":"created","wr_id":N} | {"status":"error","msg":...}
 */

// ── 안전 가드: 로컬/사설 IP에서만 동작 ───────────────────────────────────────
$remote = isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '';
$is_local = (
    $remote === '127.0.0.1' || $remote === '::1' ||
    strpos($remote, '172.') === 0 ||   // Docker 기본 브리지 대역
    strpos($remote, '10.')  === 0 ||
    strpos($remote, '192.168.') === 0 ||
    $remote === ''                      // CLI
);
if (!$is_local) {
    header('Content-Type: application/json; charset=utf-8');
    http_response_code(403);
    echo json_encode(array('status' => 'forbidden', 'msg' => 'local only'));
    exit;
}

include_once('./common.php');

header('Content-Type: application/json; charset=utf-8');

function out($arr) {
    echo json_encode($arr, JSON_UNESCAPED_UNICODE);
    exit;
}

$action = isset($_GET['action']) ? $_GET['action'] : '';

// ─────────────────────────────────────────────────────────────────────────────
// check_member
// ─────────────────────────────────────────────────────────────────────────────
if ($action === 'check_member') {
    $mb_id = isset($_GET['mb_id']) ? trim($_GET['mb_id']) : '';
    if ($mb_id === '') out(array('status' => 'error', 'msg' => 'mb_id required'));
    $mb_id = preg_replace('/[^a-z0-9_]/i', '', $mb_id);

    $row = sql_fetch("SELECT mb_id FROM {$g5['member_table']} WHERE mb_id = '{$mb_id}'");
    if (isset($row['mb_id']) && $row['mb_id'] !== '') {
        out(array('status' => 'exists', 'mb_id' => $mb_id));
    }
    out(array('status' => 'none', 'mb_id' => $mb_id));
}

// ─────────────────────────────────────────────────────────────────────────────
// create_member
// ─────────────────────────────────────────────────────────────────────────────
if ($action === 'create_member') {
    $mb_id = isset($_GET['mb_id']) ? trim($_GET['mb_id']) : '';
    $mb_pw = isset($_GET['mb_pw']) ? $_GET['mb_pw'] : 'Awt1234!';
    if ($mb_id === '') out(array('status' => 'error', 'msg' => 'mb_id required'));
    $mb_id = preg_replace('/[^a-z0-9_]/i', '', $mb_id);

    // 이미 존재?
    $row = sql_fetch("SELECT mb_id FROM {$g5['member_table']} WHERE mb_id = '{$mb_id}'");
    if (isset($row['mb_id']) && $row['mb_id'] !== '') {
        out(array('status' => 'exists', 'mb_id' => $mb_id));
    }

    $enc   = get_encrypt_string($mb_pw);
    $name  = 'AWT테스터';
    $nick  = 'awt_' . $mb_id;
    $email = $mb_id . '@awt-test.com';
    $now   = G5_TIME_YMDHIS;
    $today = G5_TIME_YMD;
    $ip    = $remote ? $remote : '127.0.0.1';
    $level = isset($config['cf_register_level']) ? (int)$config['cf_register_level'] : 2;

    $sql = "
        INSERT INTO {$g5['member_table']} SET
            mb_id            = '{$mb_id}',
            mb_password      = '{$enc}',
            mb_name          = '{$name}',
            mb_nick          = '{$nick}',
            mb_nick_date     = '{$today}',
            mb_email         = '{$email}',
            mb_level         = '{$level}',
            mb_login_ip      = '{$ip}',
            mb_ip            = '{$ip}',
            mb_datetime      = '{$now}',
            mb_today_login   = '{$now}',
            mb_open          = 1,
            mb_open_date     = '{$today}',
            mb_mailling      = 0,
            mb_sms           = 0,
            mb_email_certify = '{$now}'
    ";
    $res = sql_query($sql, false);
    if ($res) {
        out(array('status' => 'created', 'mb_id' => $mb_id));
    }
    out(array('status' => 'error', 'msg' => 'insert failed'));
}

// ─────────────────────────────────────────────────────────────────────────────
// setup_board — 비밀글 사용 활성화 (선택사용=1)
// ─────────────────────────────────────────────────────────────────────────────
if ($action === 'setup_board') {
    $bo_table = isset($_GET['bo_table']) ? trim($_GET['bo_table']) : 'free';
    $bo_table = preg_replace('/[^a-z0-9_]/i', '', $bo_table);

    sql_query("UPDATE {$g5['board_table']} SET bo_use_secret = 1 WHERE bo_table = '{$bo_table}'", false);
    out(array('action' => 'setup_board', 'status' => 'ok', 'bo_table' => $bo_table));
}

// ─────────────────────────────────────────────────────────────────────────────
// find_post — 특정 회원이 작성한 게시글 검색
// ─────────────────────────────────────────────────────────────────────────────
if ($action === 'find_post') {
    $bo_table = isset($_GET['bo_table']) ? trim($_GET['bo_table']) : 'free';
    $mb_id    = isset($_GET['mb_id']) ? trim($_GET['mb_id']) : '';
    $bo_table = preg_replace('/[^a-z0-9_]/i', '', $bo_table);
    $mb_id    = preg_replace('/[^a-z0-9_]/i', '', $mb_id);

    $write_table = $g5['write_prefix'] . $bo_table;   // g5_write_free
    $row = sql_fetch("
        SELECT wr_id FROM {$write_table}
        WHERE mb_id = '{$mb_id}' AND wr_is_comment = 0
        ORDER BY wr_id DESC LIMIT 1
    ", false);
    if (isset($row['wr_id']) && (int)$row['wr_id'] > 0) {
        out(array('status' => 'found', 'wr_id' => (int)$row['wr_id']));
    }
    out(array('status' => 'none'));
}

// ─────────────────────────────────────────────────────────────────────────────
// create_post — 게시글 직접 생성 (write_token 우회)
// ─────────────────────────────────────────────────────────────────────────────
if ($action === 'create_post') {
    $bo_table = isset($_GET['bo_table']) ? trim($_GET['bo_table']) : 'free';
    $mb_id    = isset($_GET['mb_id']) ? trim($_GET['mb_id']) : '';
    $subject  = isset($_GET['subject']) ? $_GET['subject'] : 'AWT 자동화 테스트 게시글';
    $content  = isset($_GET['content']) ? $_GET['content'] : 'AWT 자동화 테스트용 게시글입니다.';
    $bo_table = preg_replace('/[^a-z0-9_]/i', '', $bo_table);
    $mb_id    = preg_replace('/[^a-z0-9_]/i', '', $mb_id);

    $write_table = $g5['write_prefix'] . $bo_table;

    // 작성자 정보
    $mb = sql_fetch("SELECT mb_id, mb_name, mb_nick FROM {$g5['member_table']} WHERE mb_id = '{$mb_id}'");
    $wr_name = (isset($mb['mb_nick']) && $mb['mb_nick'] !== '') ? $mb['mb_nick'] : $mb_id;

    $subject = addslashes($subject);
    $content = addslashes($content);
    $wr_name = addslashes($wr_name);
    $now     = G5_TIME_YMDHIS;
    $ip      = $remote ? $remote : '127.0.0.1';

    $sql = "
        INSERT INTO {$write_table} SET
            wr_num        = (SELECT IFNULL(MIN(wr_num) - 1, -1) FROM {$write_table} AS sq),
            wr_reply      = '',
            wr_parent     = 0,
            wr_is_comment = 0,
            wr_comment    = 0,
            ca_name       = '',
            wr_option     = '',
            wr_subject    = '{$subject}',
            wr_content    = '{$content}',
            wr_link1      = '',
            wr_link2      = '',
            wr_link1_hit  = 0,
            wr_link2_hit  = 0,
            wr_hit        = 0,
            wr_good       = 0,
            wr_nogood     = 0,
            mb_id         = '{$mb_id}',
            wr_password   = '',
            wr_name       = '{$wr_name}',
            wr_email      = '',
            wr_homepage   = '',
            wr_datetime   = '{$now}',
            wr_last       = '{$now}',
            wr_ip         = '{$ip}'
    ";
    $res = sql_query($sql, false);
    if (!$res) out(array('status' => 'error', 'msg' => 'insert failed'));

    $wr_id = sql_insert_id();
    // 새 글은 자기 자신을 부모로
    sql_query("UPDATE {$write_table} SET wr_parent = '{$wr_id}' WHERE wr_id = '{$wr_id}'", false);
    // 게시판 글 카운트 증가
    sql_query("UPDATE {$g5['board_table']} SET bo_count_write = bo_count_write + 1 WHERE bo_table = '{$bo_table}'", false);

    out(array('status' => 'created', 'wr_id' => (int)$wr_id));
}

out(array('status' => 'error', 'msg' => 'unknown action: ' . $action));
