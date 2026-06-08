-- AWT PostgreSQL 초기화 스크립트 (D44)
-- 실행: psql -U postgres -f installer/db_init.sql

-- DB 및 사용자 생성 (이미 존재하면 오류 무시)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'awt_user') THEN
    CREATE ROLE awt_user LOGIN PASSWORD 'changeme';
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_database WHERE datname = 'awt') THEN
    CREATE DATABASE awt OWNER awt_user ENCODING 'UTF8';
  END IF;
END $$;

-- 스키마는 DBClient.ensure_schema()가 앱 첫 실행 시 생성
-- 초기 admin 계정은 앱 최초 실행 후 CLI 또는 Admin 탭에서 생성
GRANT ALL PRIVILEGES ON DATABASE awt TO awt_user;
