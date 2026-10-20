-- 患者姓名字段：医生接诊时需要识别患者，不再只显示院内编号
ALTER TABLE mg_patient ADD COLUMN IF NOT EXISTS real_name varchar(64);

COMMENT ON COLUMN mg_patient.real_name IS '患者姓名，医生接诊时展示';

-- 既有数据先用账号回填；演示患者 zhangsan 使用真实姓名
UPDATE mg_patient
SET real_name = account
WHERE real_name IS NULL AND account IS NOT NULL;

UPDATE mg_patient
SET real_name = '张三'
WHERE account = 'zhangsan';
