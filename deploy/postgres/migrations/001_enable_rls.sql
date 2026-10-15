-- =============================================================================
-- 001_enable_rls.sql   启用数据库级行级安全策略（RLS）
-- 对应文档：《03-数据库设计说明书》§6.5
-- -----------------------------------------------------------------------------
-- 一期默认【不启用】。执行前必须依次完成以下前置条件，顺序不可颠倒：
--
--   1. 应用层已实现会话变量注入：每个事务开始时执行
--          SELECT set_config('app.current_tenant', :tenant_id, true);
--      第三个参数必须为 true（事务级）。若用会话级设置，
--      连接池复用连接时会残留上一个租户的值，导致跨租户读到他人数据。
--
--   2. 业务连接角色不具备 BYPASSRLS 属性，且不是超级用户。
--
--   3. 已完成灰度验证：先对只读表启用并观察，再覆盖写表。
--
-- 未完成上述条件就执行本脚本，表现是「表里明明有数据却查不出来」——
-- 策略不匹配任何行，且【不报错】，排查成本很高。
--
-- 用法：psql -h <host> -p 5432 -U <user> -d <db> -f 001_enable_rls.sql
-- 回滚：见文件末尾的禁用脚本。
-- =============================================================================

-- 按实际部署调整：创建业务角色（不具备 BYPASSRLS、非超级用户）
-- CREATE ROLE medguide_app LOGIN PASSWORD '<在此填写>';
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO medguide_app;

-- -----------------------------------------------------------------------------
-- 逐表启用 RLS 并创建租户隔离策略
-- 表清单不含 mg_tenant —— 该表无 tenant_id，需单独设计策略（见文件末尾）
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    v_tbl   text;
    v_tables text[] := ARRAY[
        'mg_dept','mg_sys_config','mg_user','mg_patient','mg_patient_consent',
        'mg_session','mg_session_message','mg_triage_result','mg_triage_correction',
        'mg_mdt_council','mg_emr_record','mg_emr_document','mg_appointment',
        'mg_kb_entry','mg_kb_entry_history','mg_kb_publish','mg_kb_ingest_task',
        'mg_golden_query','mg_golden_query_run','mg_model_provider','mg_audit_log',
        'mg_file'
    ];
BEGIN
    FOREACH v_tbl IN ARRAY v_tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', v_tbl);

        EXECUTE format('DROP POLICY IF EXISTS p_%1$s_tenant ON %1$I;', v_tbl);

        EXECUTE format(
            'CREATE POLICY p_%1$s_tenant ON %1$I FOR ALL TO medguide_app '
            'USING (tenant_id = current_setting(''app.current_tenant'', true)) '
            'WITH CHECK (tenant_id = current_setting(''app.current_tenant'', true));',
            v_tbl);

        RAISE NOTICE 'RLS 已启用：%', v_tbl;
    END LOOP;

    RAISE NOTICE '================================================';
    RAISE NOTICE 'RLS 启用完成，共 % 张表', array_length(v_tables, 1);
    RAISE NOTICE '请立即验证：以 medguide_app 身份注入租户后查询，';
    RAISE NOTICE '          再以未注入租户的会话查询，应返回 0 行。';
    RAISE NOTICE '================================================';
END $$;

-- -----------------------------------------------------------------------------
-- mg_tenant 单独处理
-- 该表无 tenant_id，且是租户自身的管理表。常见做法是只允许机构管理角色访问，
-- 且限定只能看到自己那条租户记录。
-- -----------------------------------------------------------------------------
-- CREATE POLICY p_mg_tenant_self ON mg_tenant FOR ALL TO medguide_app
--     USING (id = current_setting('app.current_tenant', true))
--     WITH CHECK (id = current_setting('app.current_tenant', true));


-- =============================================================================
-- 回滚脚本（禁用 RLS）
-- =============================================================================
-- DO $$
-- DECLARE
--     v_tbl text;
--     v_tables text[] := ARRAY[
--         'mg_dept','mg_sys_config','mg_user','mg_patient','mg_patient_consent',
--         'mg_session','mg_session_message','mg_triage_result','mg_triage_correction',
--         'mg_mdt_council','mg_emr_record','mg_emr_document','mg_appointment',
--         'mg_kb_entry','mg_kb_entry_history','mg_kb_publish','mg_kb_ingest_task',
--         'mg_golden_query','mg_golden_query_run','mg_model_provider','mg_audit_log',
--         'mg_file'
--     ];
-- BEGIN
--     FOREACH v_tbl IN ARRAY v_tables LOOP
--         EXECUTE format('DROP POLICY IF EXISTS p_%1$s_tenant ON %1$I;', v_tbl);
--         EXECUTE format('ALTER TABLE %I DISABLE ROW LEVEL SECURITY;', v_tbl);
--     END LOOP;
-- END $$;
