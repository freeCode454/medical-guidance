-- 患者账号：匿名设备之外增加账号/口令登录
-- 对已有数据库执行一次；新库由 init.sql 直接创建。
ALTER TABLE mg_patient ADD COLUMN IF NOT EXISTS account varchar(64);
ALTER TABLE mg_patient ADD COLUMN IF NOT EXISTS credential_hash varchar(255);
ALTER TABLE mg_patient ADD COLUMN IF NOT EXISTS fail_count integer NOT NULL DEFAULT 0;
ALTER TABLE mg_patient ADD COLUMN IF NOT EXISTS lock_until timestamptz;
ALTER TABLE mg_patient ADD COLUMN IF NOT EXISTS last_login_time timestamptz;

CREATE UNIQUE INDEX IF NOT EXISTS uk_mg_patient_tenant_account
  ON mg_patient (tenant_id, account);

COMMENT ON COLUMN mg_patient.account IS '患者登录账号，租户内唯一';
COMMENT ON COLUMN mg_patient.credential_hash IS '患者口令哈希，可空表示匿名患者';
COMMENT ON COLUMN mg_patient.fail_count IS '连续登录失败次数';
COMMENT ON COLUMN mg_patient.lock_until IS '锁定截止时间';
COMMENT ON COLUMN mg_patient.last_login_time IS '最后登录时间';
